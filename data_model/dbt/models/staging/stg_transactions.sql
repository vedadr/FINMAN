{{
    config(materialized='view')
}}

with bank_transactions as (

    select
        id::text                        as transaction_id,
        'bank_transactions'             as source_table,
        to_date(datum_transakcije, 'DD-MM-YYYY') as transaction_date,
        to_date(datum_obrade,     'DD-MM-YYYY') as processing_date,
        iznos_transakcije               as amount_bam,
        uplata_trosak_km                as net_amount_bam,
        saldo_racuna                    as running_balance,
        trim(opis)                      as description,
        valuta_transakcije              as currency,
        broj_racuna                     as account_number,
        iban,
        grupa                           as transaction_group,
        to_date(period_od, 'DD-MM-YYYY') as period_start,
        to_date(period_do, 'DD-MM-YYYY') as period_end,
        created_at

    from {{ source('raw', 'bank_transactions') }}
    where datum_transakcije is not null

),

tansakcije_09_19 as (

    select
        promet_po_partiji::text         as transaction_id,
        'tansakcije_09_19'              as source_table,
        datum_proc::date                as transaction_date,
        datum_proc::date                as processing_date,
        iznos_valuta                    as amount_bam,
        iznos_km                        as net_amount_bam,
        null::numeric                   as running_balance,
        trim(
            concat_ws(' ',
                nullif(trim(opis1), ''),
                nullif(trim(opis2), ''),
                nullif(trim(opis3_provizija), '')
            )
        )                               as description,
        valuta                          as currency,
        na_partiju                      as account_number,
        null::text                      as iban,
        vrsta_transakcije               as transaction_group,
        null::date                      as period_start,
        null::date                      as period_end,
        null::timestamptz               as created_at

    from {{ source('raw', 'tansakcije_09_19') }}
    where datum_proc is not null

)

select * from bank_transactions
union all
select * from tansakcije_09_19
