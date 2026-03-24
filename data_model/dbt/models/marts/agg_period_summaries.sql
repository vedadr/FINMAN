{{
    config(materialized='table')
}}

with statements as (

    select * from {{ ref('stg_bank_statements') }}

),

period_transactions as (

    select
        period_start,
        period_end,
        count(*)                                                as transaction_count,
        sum(case when is_income  then net_amount_bam end)       as total_income,
        sum(case when is_expense then abs(net_amount_bam) end)  as total_expense,
        sum(net_amount_bam)                                     as net_cashflow

    from {{ ref('fct_transactions') }}
    where period_start is not null
    group by period_start, period_end

)

select
    s.period_start,
    s.period_end,
    s.account_number,
    s.iban,
    s.opening_balance,
    s.closing_balance,
    s.net_change,
    s.credit_limit,
    t.transaction_count,
    t.total_income,
    t.total_expense,
    t.net_cashflow

from statements s
left join period_transactions t
    on t.period_start = s.period_start
    and t.period_end  = s.period_end

order by s.period_start
