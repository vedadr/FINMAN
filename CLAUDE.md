# FINMAN — CLAUDE.md

Developer guide for working on this codebase with Claude Code.

---

## Project Overview

FINMAN is a conversational financial data agent. Users ask plain-English questions about their bank transactions; the agent converts them to SQL, queries Supabase, and renders interactive Plotly charts in a Streamlit UI.

The repo has three top-level components:

| Directory | Purpose |
|---|---|
| `agent/` | LangGraph + Streamlit application (the runnable app) |
| `data_model/dbt/` | dbt project — staging models and mart aggregations |
| `terraform/` | GCP Free Tier infrastructure (e2-micro VM) |

---

## Agent (`agent/`)

### Entry point
`main.py` — Streamlit chat UI that drives the LangGraph graph.

### Structure

```
agent/
├── main.py                    # Streamlit UI + graph invocation
├── graph/
│   ├── graph.py               # LangGraph graph definition
│   ├── state.py               # AgentState TypedDict
│   └── nodes/                 # One file per graph node
├── tools/
│   ├── supabase_client.py     # psycopg2 / Supabase RPC SQL execution
│   └── viz_tools.py           # Plotly chart generation
└── utils/
    ├── schema_annotations.py  # Persist/load column descriptions
    └── schema_utils.py        # Supabase information_schema introspection
```

### Tech stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph (stateful graph, interrupt support) |
| LLM | OpenAI GPT-4o |
| Database | Supabase (PostgreSQL) |
| SQL execution | psycopg2 direct (`SUPABASE_DB_URL`) or Supabase RPC fallback |
| Visualization | Plotly |
| UI | Streamlit |
| Env management | python-dotenv |

### Graph nodes

1. **init_router** — checks if schema is already loaded; routes accordingly
2. **schema_scanner** — queries `information_schema`, uses GPT-4o to infer column meanings
3. **clarifier** — pauses graph via `interrupt()`, asks user to describe ambiguous columns
4. **sql_generator** — converts the user's question to a `SELECT` query using schema context
5. **data_fetcher** — executes the query; triggers a retry back to `sql_generator` on error (max 2×)
6. **visualizer** — generates Plotly chart code via GPT-4o when visualization is requested

### Environment variables (`.env`)

```
OPENAI_API_KEY
SUPABASE_URL
SUPABASE_SECRET_KEY        # Settings → API → Secret key
SUPABASE_PUBLISHABLE_KEY   # Settings → API → Publishable key
SUPABASE_DB_URL            # Recommended — enables direct psycopg2 execution
```

### Running locally

```bash
cd agent
pip install -r requirements.txt   # or: uv sync
streamlit run main.py
```

### SQL execution modes

| Mode | Env var | Notes |
|---|---|---|
| Direct (psycopg2) | `SUPABASE_DB_URL` set | Recommended |
| Supabase RPC | `SUPABASE_DB_URL` not set | Requires `execute_query` function in DB |

---

## dbt Data Model (`data_model/dbt/`)

**Profile:** `finman` — connects to Supabase PostgreSQL.

### Layer layout

```
models/
├── staging/          # Views — clean & normalise raw source tables
│   ├── stg_transactions.sql
│   ├── stg_bank_statements.sql
│   ├── _sources.yml
│   └── _staging.yml
└── marts/            # Tables — aggregations consumed by the agent
    ├── fct_transactions.sql
    ├── agg_monthly_cashflow.sql
    ├── agg_expense_trends.sql
    ├── agg_daily_cashflow.sql
    ├── agg_balance_over_time.sql
    ├── agg_period_summaries.sql
    └── _marts.yml
```

### Source tables (raw schema)

- `bank_transactions` — primary transaction ledger
- `tansakcije_09_19` — historical transaction dump (note the typo in the source table name)

### Key patterns & recent fixes

**Date parsing** — Raw source columns (`datum_transakcije`, `datum_obrade`, `period_od`, `period_do`) store dates as `VARCHAR` in `DD-MM-YYYY` format. Always use `to_date(col, 'DD-MM-YYYY')` instead of a direct `::date` cast.

```sql
-- correct
to_date(datum_transakcije, 'DD-MM-YYYY') as transaction_date

-- wrong (breaks on DD-MM-YYYY strings)
datum_transakcije::date
```

**`round()` with window functions** — PostgreSQL's `round()` requires an explicit `::numeric` cast when the argument is an expression involving window functions or division. Wrap the expression before casting:

```sql
-- correct
round((100.0 * (a - b) / nullif(b, 0))::numeric, 2)

-- wrong (type error at runtime)
round(100.0 * (a - b) / nullif(b, 0), 2)
```

**dbt `accepted_values` test syntax** — Use the `arguments:` key (dbt ≥ 1.9 style):

```yaml
tests:
  - accepted_values:
      arguments:
        values: ["bank_transactions", "tansakcije_09_19"]
```

**`.gitignore` additions** — `.venv/` and `package-lock.yml` are ignored inside `data_model/dbt/`.

### Running dbt

```bash
cd data_model/dbt
dbt run
dbt test
```

---

## Terraform / Deployment (`terraform/`)

Provisions a **free** GCP e2-micro VM to host the Streamlit app.

### Resources

- 1 × `e2-micro` instance (us-west1 / us-central1 / us-east1 — free tier regions)
- 30 GB `pd-standard` boot disk
- Ephemeral external IP
- 1 GB swap file (auto-created by `startup.sh.tpl` — prevents OOM during pip install)

### Files

| File | Purpose |
|---|---|
| `main.tf` | VM, firewall, and networking resources |
| `variables.tf` | Input variable declarations |
| `outputs.tf` | `app_url`, `ssh_command`, `deploy_command`, `startup_log_command` |
| `startup.sh.tpl` | Cloud-init bootstrap script (installs deps, creates systemd service) |
| `terraform.tfvars.example` | Template — copy to `terraform.tfvars` and fill in secrets |

### Deploy

```bash
gcloud auth application-default login
cd terraform
cp terraform.tfvars.example terraform.tfvars   # fill in project_id + secrets
terraform init
terraform plan
terraform apply
```

### Manage the VM

```bash
# Copy app files
gcloud compute scp --recurse ./agent finman-app:/opt/finman/ --zone=us-central1-a

# Systemd service
sudo systemctl status finman
sudo systemctl restart finman
sudo journalctl -u finman -f
sudo cat /var/log/finman-startup.log
```

---

## Dependency management

The agent uses both `requirements.txt` (pip) and `pyproject.toml` / `uv.lock` (uv). Either works; uv is faster.

---

## Future work (tracked here for context)

1. **Multi-turn memory** — `MemorySaver` with a shared thread so follow-up questions work without repeating context.
2. **Persistent schema annotations** — Write clarified column descriptions to a `_finman_schema_annotations` Supabase table instead of session memory.
3. **Query history & saved insights** — Bookmark queries/charts; re-run or schedule them.
4. **Multi-database support** — Connect to multiple Supabase projects or other PostgreSQL-compatible DBs.
5. **Anomaly detection** — Proactively surface statistical anomalies in key metrics.