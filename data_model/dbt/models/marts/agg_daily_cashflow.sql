{{
    config(materialized='table')
}}

select
    transaction_date,
    count(*)                                            as transaction_count,
    sum(case when is_income  then net_amount_bam end)   as total_income,
    sum(case when is_expense then abs(net_amount_bam) end) as total_expense,
    sum(net_amount_bam)                                 as net_cashflow

from {{ ref('fct_transactions') }}
group by transaction_date
order by transaction_date
