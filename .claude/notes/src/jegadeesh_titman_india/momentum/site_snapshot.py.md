# site_snapshot.py

## Why cohorts, not holdings

A J/K portfolio's holdings in month m are the winners decile of the cohorts formed at the ends of months m−K to m−1, each with 1/K of the money and equal weights within it. The holding period K therefore only changes how many cohorts are combined, so storing the winners decile at every month-end for each ranking period, gap and universe (4 × 2 × 2 = 16 files) is enough to rebuild all 64 portfolios, their joiners and leavers, and their history. Storing holdings directly would need 64 files and roughly four times the space.

Each cohort row is `[symbol number, ranking return, traded value in crore, liquidity tercile]`, sorted by ranking return. Symbol numbers index `meta.json`'s `symbols` list, which keeps the files small: 8.8 MB for all 19 files, of which a page loads about 1.3 MB for an all-shares strategy or 0.7 MB for a top-500 one.

## What is and is not published

Only the study's derived output is written: which shares were winners, their ranking returns and median traded values, and the strategies' monthly returns. No daily NSE prices are included, so the snapshot is not a copy of NSE's data.

## Holdings in the app versus the backtest

The backtest drops a share from a cohort's average in a month in which it did not trade, and the live code keeps only shares that traded in the last month. The app shows every member of every cohort, because it reads only the cohort lists. The difference matters only for shares that stopped trading during a holding period, which is rare among the 500 most traded.

## Paper's Table I

`paper_table_one.csv` holds the buy-minus-sell row of the paper's Table I, both panels, typed in from the PDF. It is a data file rather than a constant so the code keeps one element per line without 200 lines of numbers.
