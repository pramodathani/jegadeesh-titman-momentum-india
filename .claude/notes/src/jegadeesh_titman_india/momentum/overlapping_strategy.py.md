# overlapping_strategy.py

## Mechanics, following Section I of the paper

At the end of each month t, shares are put into deciles on their J-month return. A cohort formed at t is held in months t+1 to t+K. In any month the strategy holds the K most recent cohorts, each with 1/K of the money, and within a cohort every share has equal weight, rebalanced monthly. The paper reports these rebalanced returns because buy-and-hold returns were "very similar".

A month's portfolio return is reported only when all K cohorts exist, so the first K months after the first formation are blank.

## Shares that stop trading

A share with no return in a holding month drops out of its cohort's average for that month, and the cohort's weight is spread over the shares still trading. With the bhavcopy data a delisting share's last partial month is still included, so its final fall is counted.

## Turnover

Turnover is measured against weights drifted by last month's returns, so it counts the trades needed to rebalance as well as those from cohorts entering and leaving. The paper quotes 84.8% one-way turnover per six months for its long-short portfolio. A share that stopped trading is treated as sold at no cost, which slightly understates costs.
