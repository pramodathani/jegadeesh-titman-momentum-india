# momentum_study.py

## Choices that differ from the paper

| Paper | This study | Why |
|---|---|---|
| NYSE and AMEX, every stock | All NSE shares, and separately the 500 most traded | Indian microcaps are often untradeable, so results on the liquid half matter more for practice |
| Size subsamples by market capitalisation | Terciles by median daily traded value | No market capitalisation in either data source |
| Beta subsamples | Not done | Would need daily betas re-estimated each year; left for later |
| CRSP value- and equal-weighted indices as market | NIFTY 500 with its dividend yield added (approximate total return) for the bhavcopy study, NIFTY 500 price return for the quick pass, and an equal-weighted average of all shares in the panel for both | The strategy's bhavcopy returns include dividends, so the benchmark should too; see `benchmark_history.py.md`. The equal-weighted market is built from the data itself and covers every period |
| Treasury bill rate in excess returns | No risk-free rate | Not available; alphas are market-model intercepts |
| Earnings announcement returns (Table IX) | Not done | No results dates available |

## Samples

Table I uses the months common to all 32 strategies, as the paper did. The 6/6 tables use every month the 6/6 strategy has, which for the quick pass starts a year earlier than Table I.

## Event time

Monthly event-time t-statistics use Newey-West errors with 6 lags, because neighbouring cohorts share most of their shares. Cumulative returns at horizon h use only cohorts that have all h months, so the cumulative column is not exactly the running sum of the monthly column near the end of the sample.

## March

India's financial year ends on 31 March, so any tax-loss selling falls in March rather than December. The calendar-month table is where a March effect would show, playing the part of the paper's January.

## Why the class is separate from the scripts

The study used to choose its price source itself, which meant importing `tradingmachine` even for the bhavcopy study. It now takes the daily rows and benchmark returns as arguments, so `scripts/run_study.py` (bhavcopy) never imports `tradingmachine` and the published repository can be run without it. `scripts/run_quick_pass_study.py` does the same for tradingmachine's prices.
