{{
    config(materialized='table')
}}

with monthly as (

    select
        transaction_month                               as month,
        year,
        month_num,
        count(*)                                        as transaction_count,
        sum(case when is_income  then net_amount_bam end)           as total_income,
        sum(case when is_expense then abs(net_amount_bam) end)      as total_expense,
        sum(net_amount_bam)                             as net_cashflow

    from {{ ref('fct_transactions') }}
    group by transaction_month, year, month_num

)

select
    month,
    year,
    month_num,
    transaction_count,
    total_income,
    total_expense,
    net_cashflow,

    -- Month-over-month
    lag(net_cashflow) over (order by month)             as prev_month_net_cashflow,
    round(
        100.0 * (net_cashflow - lag(net_cashflow) over (order by month))
            / nullif(abs(lag(net_cashflow) over (order by month)), 0),
        2
    )                                                   as mom_pct_change,

    lag(total_expense) over (order by month)            as prev_month_expense,
    round(
        100.0 * (total_expense - lag(total_expense) over (order by month))
            / nullif(lag(total_expense) over (order by month), 0),
        2
    )                                                   as mom_expense_pct_change

from monthly
order by month
