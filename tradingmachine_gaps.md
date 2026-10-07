# Gaps in tradingmachine found during the momentum study

This file records what the Jegadeesh and Titman (1993) study needed from `tradingmachine` and its Unified Broker Interface (UBI) but could not get, so that the gaps can be considered as library changes later. Each entry says what was missing, how the study worked around it, and what a fix might look like.

| # | Gap | How the study worked around it | Possible fix |
|---|---|---|---|
| 1 | Daily share prices start on 3 December 2019 | A second data track builds history from NSE bhavcopy files back to 1995 | Backfill `unified.price_history` for NSE cash shares from bhavcopy, or from Zerodha or Dhan with adjustment factors removed |
| 2 | Only shares listed today are covered, so delisted shares are missing (survivorship bias) | The bhavcopy track keeps every share that ever traded | Keep instruments that leave the broker masters, with a delisting date |
| 3 | Of 3,423 listed NSE shares in UBI's master, 817 have no daily prices at all | They are left out of the quick pass | Check why `POST /api/instruments/prices` returns no candles for them |
| 4 | A renamed share's history stops at the rename: ETERNAL (formerly ZOMATO) has bars only up to 2025-04-08 | Treated as if the share delisted | Link a share's history across symbol changes, for example by ISIN |
| 5 | A few shares miss their latest days: YESBANK's last bar is 2026-10-01 while most end on 2026-10-06 | Not material for monthly returns | Look for gaps in the daily loader |
| 6 | 84 daily returns in 71 shares are below -50% or above +100%, almost all splits or bonuses that were not adjusted, such as PGEL on 2024-07-10 (-99%) | Such returns are set to zero | Have the adjustment-factor verification flag these days |
| 7 | Prices are adjusted for splits and bonuses but not dividends, so returns are price-only | The bhavcopy track adds dividends from NSE's corporate action list | Add dividend factors to `unified.adjustment_factors`, or store a total-return series |
| 8 | No list of corporate action events that a caller can query | The study downloads NSE's list from `https://www.nseindia.com/api/corporates-corporateActions` | Store NSE's corporate actions in UBI and serve them |
| 9 | `Instrument.prices` does not pass UBI's `known_as_of` argument | Not needed here, because returns computed from back-adjusted prices are the same whenever the factor became known | Add a `known_as_of` parameter to `Instrument.prices` |
| 10 | No market capitalisation or shares outstanding | Median daily traded value stands in for size | Add shares outstanding, for example from NSE's quarterly shareholding filings |
| 11 | No index constituents, current or historical | "Most traded 500" stands in for the Nifty 500 | Fill `BasketStore` from NSE's index constituent files |
| 12 | Index levels are price indices; no total-return indices | Benchmarks are price returns, which understates them by roughly the dividend yield, about 1 to 1.5 percent a year | Add NSE's total-return index series |
| 13 | No cross-sectional backtester: `StrategyBacktests` runs one instrument and `AssetBasket.prices` holds fixed quantities | The study has its own ranking, overlapping-portfolio and turnover code | A portfolio simulator that rebalances to target weights each period |
| 14 | `PerformanceMeasures` works only on instruments and baskets, not on a plain return series | The study computes alpha and beta with statsmodels | Let the measures accept a pandas Series of returns |
| 15 | No risk-free rate series | Alphas are market-model intercepts without a risk-free rate | Add the RBI 91-day Treasury bill yield |
| 16 | No earnings announcement dates | The paper's Table IX is not replicated | Store results dates from NSE's financial results filings |

## Gaps found while building live portfolios

| # | Gap | How the study worked around it | Possible fix |
|---|---|---|---|
| 17 | A strategy cannot own part of an account: `Portfolio.from_holdings` reads the whole demat account, so `rebalance` towards a target would sell every unrelated holding | Each strategy keeps its own book, a `Portfolio` stored in the `BasketStore` as `<strategy>-holdings` | A sub-portfolio or "sleeve" concept, with holdings attributed by order tag |
| 18 | `Portfolio` refuses to be empty, so a strategy's first purchase and a fully sold book need special handling | The first rebalance uses `Index.to_portfolio`, and a fully sold book is not saved | Allow an empty `Portfolio` |
| 19 | `rebalance` sends sells and buys in one request, so delivery buys must be affordable before the sales settle | Sells are sent first, then buys after the fills are read | A `sells_first` option on `rebalance` |
| 20 | Nothing reports how much of a list of orders filled; the marketable limits can part-fill and are cancelled after 30 seconds | `FillReconciler` reads `/api/orders/details` and matches on `intent_id` or `order_id` | A `fills` method that takes `place_orders` results |
| 21 | `Index.to_portfolio` floors every quantity, so with many members and modest capital, expensive shares get zero units: ₹10 lakh across 118 targets invested only 87.6% | Reported in each run's summary | Optional largest-remainder rounding that spends the leftover cash |
| 22 | No funds or margin check before buying | UBI rejects orders that cannot be paid for | A `funds` reading to size purchases |
