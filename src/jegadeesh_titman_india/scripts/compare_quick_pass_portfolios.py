"""Scores all 64 long-only winners portfolios on tradingmachine's prices, as a cross-check of the bhavcopy comparison.

Run from the repository root after fetch_tradingmachine_prices:

  python -m jegadeesh_titman_india.scripts.compare_quick_pass_portfolios

The table is written to `results/portfolio_comparison/tradingmachine.csv`.
"""

import logging
import pathlib

import pandas as pd

from jegadeesh_titman_india.momentum import implausible_move_filter
from jegadeesh_titman_india.momentum import monthly_return_panel
from jegadeesh_titman_india.momentum import portfolio_comparison
from jegadeesh_titman_india.momentum.price_sources import tradingmachine_price_source


STUDY_DIRECTORY = pathlib.Path(__file__).resolve().parents[3]

DATA_DIRECTORY = STUDY_DIRECTORY / 'data'

OUTPUT_DIRECTORY = STUDY_DIRECTORY / 'results' / 'portfolio_comparison'

LAST_COMPLETE_DAY = pd.Timestamp('2026-09-30')

BENCHMARK = 'NIFTY 500'

SHOWN_COLUMNS = [
    'compound_annual',
    'excess_annual',
    'excess_t',
    'sharpe',
    'maximum_drawdown',
    'excess_first_half',
    'excess_second_half',
    'annual_turnover',
]


class CompareQuickPassPortfoliosApplication:
    """The command-line program that scores the 64 portfolios on the tradingmachine prices."""

    def run(self) -> None:
        """Builds the panel, scores the portfolios, and writes and prints the table.

        Returns:
            None.

        Raises:
            FileNotFoundError: The tradingmachine cache has not been filled.
        """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        source = tradingmachine_price_source.TradingmachinePriceSource(DATA_DIRECTORY / 'tradingmachine')
        daily_panel = source.daily_panel()
        daily_panel = implausible_move_filter.ImplausibleMoveFilter().clean(daily_panel[daily_panel['date'] <= LAST_COMPLETE_DAY])
        panel = monthly_return_panel.MonthlyReturnPanel(daily_panel)
        closes = source.index_closes()
        closes = closes[closes.index <= LAST_COMPLETE_DAY]
        benchmark = closes.groupby(closes.index.to_period('M')).last()[BENCHMARK].pct_change()
        comparison = portfolio_comparison.PortfolioComparison(panel, benchmark, BENCHMARK)
        table = comparison.table()
        OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
        table.to_csv(OUTPUT_DIRECTORY / 'tradingmachine.csv')
        print(f'{len(table)} portfolios, {table["months"].iloc[0]} months from {table["first_month"].iloc[0]} to {table["last_month"].iloc[0]}; {BENCHMARK} price return compound annual {table["benchmark_compound_annual"].iloc[0]:.2%}')
        print(table[SHOWN_COLUMNS].round(3).to_string())


if __name__ == '__main__':
    CompareQuickPassPortfoliosApplication().run()
