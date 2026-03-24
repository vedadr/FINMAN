{{
    config(materialized='table')
}}

-- Monthly expense totals per category with MoM and YoY % change.
-- Add rows to seeds/transaction_categories.csv to improve categorisation.

with monthly_by_category as (

    select
        transaction_month                               as month,
        year,
        month_num,
        category,
        count(*)                                        as transaction_count,
        sum(abs(net_amount_bam))                        as total_expense

    from {{ ref('fct_transactions') }}
    where is_expense
    group by transaction_month, year, month_num, category

)

select
    month,
    year,
    month_num,
    category,
    transaction_count,
    total_expense,

    -- Month-over-month
    lag(total_expense, 1) over (
        partition by category order by month
    )                                                   as prev_month_expense,
    round(
        (100.0 * (
            total_expense
            - lag(total_expense, 1) over (partition by category order by month)
        ) / nullif(
            lag(total_expense, 1) over (partition by category order by month),
            0
        ))::numeric,
        2
    )                                                   as mom_pct_change,

    -- Year-over-year (same month, prior year)
    lag(total_expense, 12) over (
        partition by category order by month
    )                                                   as prev_year_expense,
    round(
        (100.0 * (
            total_expense
            - lag(total_expense, 12) over (partition by category order by month)
        ) / nullif(
            lag(total_expense, 12) over (partition by category order by month),
            0
        ))::numeric,
        2
    )                                                   as yoy_pct_change

from monthly_by_category
order by month desc, total_expense desc
