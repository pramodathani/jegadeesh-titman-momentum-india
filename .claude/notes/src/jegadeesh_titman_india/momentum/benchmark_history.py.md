# benchmark_history.py

## Sources

| Source | Covers | Gives | Who can get it |
|---|---|---|---|
| NSE daily index files, `ind_close_all_DDMMYYYY.csv` on `nsearchives.nseindia.com/content/indices/` | July 2012 onward (earlier dates answer 404) | Close and dividend yield for every NSE index | Anyone |
| tradingmachine cache, `data/tradingmachine/daily_index_prices.parquet` | 2005 onward | Close only | Someone running UBI |

The NIFTY 500 has had three names in NSE's files: `S&P CNX 500`, `CNX 500` and `Nifty 500`. The Nifty Indices history service (`niftyindices.com/Backpage.aspx/...`) answers scripted requests with an error and a redirect, so it is not used.

Monthly returns are spliced, not levels: NSE's returns are used for every month they cover, and the cache's returns only for months before NSE's first month. A reader without the cache therefore gets a benchmark from July 2012 only, and comparisons start then.

## Approximate total return

The strategy's bhavcopy returns include dividends, while index levels do not, so comparing them flatters the strategy by roughly the index's dividend yield, about 1 to 1.5% a year. The total return here adds one twelfth of the month's average dividend yield to the month's price return. Before July 2012 no yield is available and the average of the later years' yield is used. NSE also publishes a NIFTY 500 Total Return Index, which would be exact, but its history was not found in a scriptable archive.
