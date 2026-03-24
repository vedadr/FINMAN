{{
    config(materialized='table')
}}

-- Daily closing balance per account.
-- Uses the last recorded running_balance for each date.
-- Only rows from bank_transactions have running_balance populated.

with ranked as (

    select
        transaction_date,
        account_number,
        running_balance,
        row_number() over (
            partition by transaction_date, account_number
            order by transaction_id desc
        ) as rn

    from {{ ref('fct_transactions') }}
    where running_balance is not null

)

select
    transaction_date,
    account_number,
    running_balance

from ranked
where rn = 1
order by account_number, transaction_date
