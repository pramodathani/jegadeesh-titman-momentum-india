# monthly_return_panel.py

Monthly returns compound daily returns within each calendar month, as the paper did with CRSP daily returns (its footnote 4).

Ranking returns are measured from wealth indices, the cumulative product of daily returns, read at month-end trading days. For the "skip a week" strategies of the paper's Panel B the end point moves back five trading days, while the holding period still starts on the first day of the next month, so the last week of the formation month is in neither period.

A share's wealth index is 1 before it lists, so a ranking period starting before listing would be wrong. `UniverseFilter.eligible` therefore requires the share to have traded in J + 1 consecutive months, including the month whose last day starts the ranking period.

Traded value is the median daily traded value in each month, and liquidity rankings use its average over six months. The median is used because a single block deal can make one day's traded value many times the usual figure.
