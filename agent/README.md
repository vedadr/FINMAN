<p align="center">
  <img src="../logo.png" alt="FINMAN logo" width="120" />
</p>

# FINMAN Data Agent

A conversational data agent that lets you query your Supabase database in plain English, infer meaning from your schema, and visualize results interactively — no SQL knowledge required.

---

## Goal

FINMAN Agent bridges the gap between raw database data and business insight. Instead of writing SQL or navigating BI dashboards, you describe what you want in plain English. The agent translates your intent into a safe SQL query, fetches the data, and renders an interactive chart — all inside a chat interface.

It also acts as a living data dictionary: on startup it scans your schema, uses an LLM to infer what each column means, and asks you to clarify anything it cannot confidently interpret. Those descriptions are then used to generate better, more accurate SQL throughout your session.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) — stateful agent graph with interrupt support |
| LLM | OpenAI GPT-4o — schema inference, text-to-SQL, visualization code generation |
| Database | [Supabase](https://supabase.com) (PostgreSQL) — schema introspection and query execution |
| SQL Execution | psycopg2 (direct connection via `SUPABASE_DB_URL`) or Supabase RPC fallback |
| Visualization | [Plotly](https://plotly.com/python/) — interactive charts rendered in the browser |
| UI | [Streamlit](https://streamlit.io) — chat-style web interface |
| Environment | python-dotenv — credential management via `.env` |

---

## Architecture

```
  User (Streamlit chat)
        │
        │  plain-English question
        ▼
┌───────────────────────────────────────────────────────┐
│                   LangGraph Agent                     │
│                                                       │
│   ┌─────────────┐                                     │
│   │ init_router │  ◄── on every invocation            │
│   └──────┬──────┘                                     │
│          │                                            │
│    schema │ already         no schema yet             │
│    loaded │◄──────────────────────────────┐           │
│          │                               │           │
│          ▼                               ▼           │
│   ┌─────────────┐              ┌──────────────────┐  │
│   │sql_generator│              │ schema_scanner   │  │
│   │  (GPT-4o)  │              │  (GPT-4o +       │  │
│   └──────┬──────┘              │  Supabase        │  │
│          │                    │  information_    │  │
│          ▼                    │  schema)         │  │
│   ┌─────────────┐              └────────┬─────────┘  │
│   │data_fetcher │                       │            │
│   │ (SQL exec)  │◄──retry on error      ▼            │
│   └──────┬──────┘              ┌──────────────────┐  │
│          │                    │    clarifier     │  │
│    viz?  │                    │  (interrupt() ── │  │
│   yes ▼  │ no                 │   asks user)     │  │
│   ┌──────────┐  ──► table     └──────────────────┘  │
│   │visualizer│                                       │
│   │(GPT-4o + │                                       │
│   │ Plotly)  │                                       │
│   └──────────┘                                       │
└───────────────────────────────────────────────────────┘
        │
        │  DataFrame table  /  Plotly chart
        ▼
  User (Streamlit chat)
```

**Session flow:**

```
1. App starts
   └─► schema_scanner queries information_schema
       └─► GPT-4o infers column descriptions
           ├─► ambiguous columns? ──► clarifier pauses graph
           │                          user fills in a form
           │                          graph resumes with answers
           └─► schema ready

2. User asks a question
   └─► sql_generator builds a SELECT query (with schema context)
       └─► data_fetcher executes query against Supabase
           ├─► error? ──► sql_generator retries (max 2x)
           ├─► visualization requested? ──► visualizer generates Plotly chart
           └─► result displayed as table + optional chart
```

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and fill in:
#   OPENAI_API_KEY
#   SUPABASE_URL
#   SUPABASE_SECRET_KEY       (Settings → API → Secret key)
#   SUPABASE_PUBLISHABLE_KEY  (Settings → API → Publishable key)
#   SUPABASE_DB_URL           (recommended — enables direct psycopg2 SQL execution)

# 3. Run
streamlit run main.py
```

### SQL execution modes

| Mode | Setup | When to use |
|---|---|---|
| Direct (psycopg2) | Set `SUPABASE_DB_URL` in `.env` | Recommended — no extra DB setup |
| Supabase RPC | Create `execute_query` function in DB | When direct connection is not available |

**RPC function** (only needed if `SUPABASE_DB_URL` is not set):

```sql
CREATE OR REPLACE FUNCTION execute_query(query text)
RETURNS json LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE result json;
BEGIN
  EXECUTE 'SELECT json_agg(t) FROM (' || query || ') t' INTO result;
  RETURN COALESCE(result, '[]'::json);
END;
$$;
```

---

## Deployment — GCP Free Tier

The `terraform/` directory at the repo root contains a Terraform script that provisions a **free** Google Cloud VM to host the app permanently.

**Free tier resources used:**
- 1 × `e2-micro` non-preemptible instance (us-west1 / us-central1 / us-east1)
- 30 GB `pd-standard` boot disk
- Ephemeral external IP

### Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) ≥ 1.5
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`)
- A GCP project with the Compute Engine API enabled

### Steps

```bash
# 1. Authenticate
gcloud auth application-default login

# 2. Configure variables
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — fill in project_id and all secrets

# 3. Deploy
terraform init
terraform plan
terraform apply
```

After `apply`, Terraform prints:

| Output | Description |
|---|---|
| `app_url` | URL to open the Streamlit app in the browser |
| `ssh_command` | `gcloud compute ssh` command to log into the VM |
| `deploy_command` | `gcloud compute scp` command to copy app files |
| `startup_log_command` | Stream the VM bootstrap log |

### Deploy app files (if no `repo_url` set)

```bash
# From the repo root — run the deploy_command shown in terraform output:
gcloud compute scp --recurse ./agent finman-app:/opt/finman/ --zone=us-central1-a

# Then start the service on the VM:
gcloud compute ssh finman-app --zone=us-central1-a \
  --command="sudo systemctl start finman"
```

### Useful VM commands

```bash
# Check service status
sudo systemctl status finman

# View live logs
sudo journalctl -u finman -f

# Restart after a code update
sudo systemctl restart finman

# View startup script log
sudo cat /var/log/finman-startup.log
```

> **Note:** The VM has 1 GB RAM. A 1 GB swap file is created automatically by the startup script to prevent out-of-memory crashes during dependency installation and heavy LLM calls.

---

## Future Development

### 1. Multi-turn conversational memory
The agent currently handles each query independently. Adding cross-query memory (e.g. via LangGraph's `MemorySaver` with a shared thread across queries) would allow follow-up questions like *"now filter that by last quarter"* or *"break the previous result down by region"* without repeating context.

### 2. Persistent schema annotations
Column descriptions clarified by the user are currently session-only. Persisting them to a dedicated Supabase metadata table (e.g. `_finman_schema_annotations`) would mean the agent remembers your data dictionary across sessions and deployments, eliminating repeated clarification.

### 3. Query history and saved insights
Allow users to bookmark queries and charts, giving them a named library of reusable insights (e.g. *"Monthly Revenue by Product"*). These could be re-run on demand or scheduled, turning the agent into a lightweight automated reporting tool.

### 4. Multi-database / multi-schema support
Extend the connection layer to support multiple Supabase projects, or other PostgreSQL-compatible databases (Neon, AlloyDB, RDS). A sidebar connection switcher would let analysts work across environments without restarting the app.

### 5. Anomaly detection and proactive alerts
Rather than only answering reactive questions, the agent could periodically scan key metrics for statistical anomalies (sudden drops, outliers, missing data) and proactively surface findings in the chat — turning FINMAN into an always-on data watchdog rather than a query tool.
