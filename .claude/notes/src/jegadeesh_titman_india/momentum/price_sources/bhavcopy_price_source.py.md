# bhavcopy_price_source.py

## Why corporate actions are applied by hand

The original plan assumed NSE's `PREVCLOSE` column is adjusted on a split or bonus ex-date, so that `CLOSE / PREVCLOSE - 1` would be a clean return. That was checked on 2026-10-07 against two known events and is **false**:

| Date | Share | Close | PREVCLOSE | Naive return |
|---|---|---|---|---|
| 2018-09-04 | INFY, 1:1 bonus | 737.15 | 1434.25 | -48.6% |
| 2021-10-28 | IRCTC, 1:5 split | 913.50 | 4130.15 | -77.9% |

So the source applies NSE's own corporate action list (see `bhavcopy/corporate_action_parser.py.md`). A useful side effect is that dividends are applied too, which makes these total returns, closer to CRSP than the price-only returns from tradingmachine.

## The "factor must help" guard

A split or bonus factor is applied only if it brings that day's return closer to zero in log terms. This protects against wrong ex-dates, a symbol in the action list that belongs to a different instrument (for example `UTIUS64-CI`, "Split Us 64 Into 2 Parts", parsed as a factor of 32), and duplicate listings. The counts of matched versus applied factors are reported in each run's summary.

## Dividends

A dividend larger than half the previous close is ignored, because such values are almost always parsing or data errors. A dividend on the same day as a split is assumed to be quoted per pre-split share; this is ambiguous but rare.

## Series

`EQ`, `BE` and `BZ` are kept because shares move into trade-for-trade (`BE`) or non-compliance (`BZ`) series and back; dropping those series would break a share's return chain at exactly the moments it is in trouble, which would bias the loser decile.

## Symbol changes

Returns are chained by symbol, so a renamed share looks like one share that stopped and a new one that started. Its return up to the rename is kept, so this costs observations but does not bias returns. Linking by ISIN would be better but ISIN only appears in the older format from about 2011.

## Matching splits and bonuses to the right day

Checks on 2026-10-07 found three problems, all now handled:

| Case | What went wrong | Fix |
|---|---|---|
| SATYAMCOMP, 9 October 2006 | NSE wrote `Bonus-1:1`, and the bonus pattern expected a space | The parser accepts `-` or `:` after "bonus" |
| NAZARA, 26 September 2025 | A 1:1 bonus and a Rs 4 to Rs 2 split were listed as two actions; each was matched alone, and the parser also dropped the split as a duplicate because both had a factor of 2 | Duplicates are now judged by description, and actions on the same share and ex-date are multiplied together before matching |
| Some listed ex-dates | A few days away from the day the price actually adjusted | Each combined action is placed on the trading day from 7 days before to 10 days after the listed ex-date whose unadjusted return best fits the ratio |

Some bonuses are missing from NSE's list altogether, notably in 2005 (M&M, Wipro, Havells), so those days still show falls of about 50%. A missed bonus makes a share look like a loser and adds a false fall to whichever portfolio holds it that month, so it biases winners' returns down, not up.

## What the remaining large falls are

From 2005, about 2,300 one-day falls of 25 to 50% remain. About 1,750 are in shares priced under Rs 2, where NSE's 5-paise price step turns Rs 0.15 to Rs 0.10 into -33%; these are real moves in untradeable penny stocks. About 840 are in shares priced at Rs 10 or more, around 38 a year, with 106 in 2008; most of these are real crashes, frauds and demergers.
