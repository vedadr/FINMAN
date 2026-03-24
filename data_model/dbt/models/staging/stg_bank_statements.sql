{{
    config(materialized='view')
}}

-- One row per distinct bank statement period per account.
-- Deduplication keeps the latest-created row when the same period appears
-- multiple times (e.g. from duplicate email ingestion).

with ranked as (

    select
        to_date(period_od, 'DD-MM-YYYY') as period_start,
        to_date(period_do, 'DD-MM-YYYY') as period_end,
        broj_racuna                     as account_number,
        iban,
        prethodno_stanje                as opening_balance,
        konacno_stanje                  as closing_balance,
        odobreni_limit                  as credit_limit,
        created_at,
        row_number() over (
            partition by period_od, period_do, broj_racuna
            order by created_at desc
        )                               as rn

    from {{ source('raw', 'bank_transactions') }}
    where period_od is not null
      and period_do is not null

)

select
    period_start,
    period_end,
    account_number,
    iban,
    opening_balance,
    closing_balance,
    closing_balance - opening_balance   as net_change,
    credit_limit,
    created_at

from ranked
where rn = 1
