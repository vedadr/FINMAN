{{
    config(materialized='table')
}}

-- Enriched fact table: adds date parts, income/expense flags, and
-- category matched from the transaction_categories seed via keyword lookup.
-- When a description matches multiple keywords the first match wins (lowest keyword row).

with transactions as (

    select * from {{ ref('stg_transactions') }}

),

categories as (

    select
        lower(trim(keyword))    as keyword,
        category
    from {{ ref('transaction_categories') }}

),

categorized as (

    select
        t.transaction_id,
        t.source_table,
        t.transaction_date,
        t.processing_date,
        t.amount_bam,
        t.net_amount_bam,
        t.running_balance,
        t.description,
        t.currency,
        t.account_number,
        t.iban,
        t.transaction_group,
        t.period_start,
        t.period_end,
        t.created_at,

        -- Date dimensions
        date_trunc('month', t.transaction_date)::date   as transaction_month,
        date_trunc('week',  t.transaction_date)::date   as transaction_week,
        extract(year  from t.transaction_date)::int     as year,
        extract(month from t.transaction_date)::int     as month_num,
        extract(quarter from t.transaction_date)::int   as quarter,

        -- Direction flags
        t.net_amount_bam > 0    as is_income,
        t.net_amount_bam < 0    as is_expense,

        -- Category: first matching keyword, fallback to Uncategorised
        coalesce(
            (
                select c.category
                from categories c
                where lower(t.description) like '%' || c.keyword || '%'
                limit 1
            ),
            'Uncategorised'
        )                       as category

    from transactions t

)

select * from categorized
