"""Scores all 64 long-only winners portfolios on the bhavcopy data, after Indian costs, against the NIFTY 500 total return.

Run from the repository root after download_bhavcopy, build_bhavcopy_store and download_index_history:

  python -m jegadeesh_titman_india.scripts.compare_portfolios
  python -m jegadeesh_titman_india.scripts.compare_portfolios --start 2005-01-01

The table is written to `results/portfolio_comparison/bhavcopy_from_<year>.csv`.
"""

import argparse
import logging
import pathlib

import pandas as pd

from jegadeesh_titman_india.momentum import benchmark_history
from jegadeesh_titman_india.momentum import implausible_move_filter
from jegadeesh_titman_india.momentum import monthly_return_panel
from jegadeesh_titman_india.momentum import portfolio_comparison
from jegadeesh_titman_india.momentum.price_sources import bhavcopy_price_source


STUDY_DIRECTORY = pathlib.Path(__file__).resolve().parents[3]

DATA_DIRECTORY = STUDY_DIRECTORY / 'data'

OUTPUT_DIRECTORY = STUDY_DIRECTORY / 'results' / 'portfolio_comparison'

LAST_COMPLETE_DAY = pd.Timestamp('2026-09-30')

DEFAULT_START = pd.Timestamp('2005-01-01')

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


class ComparePortfoliosApplication:
    """The command-line program that scores the 64 portfolios on the bhavcopy data."""

    def run(self) -> None:
        """Builds the panel, scores the portfolios, and writes and prints the table.

        Returns:
            None.

        Raises:
            FileNotFoundError: The bhavcopy store or the index history has not been built.
        """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        parser = argparse.ArgumentParser(description='Score the 64 long-only momentum portfolios on bhavcopy data.')
        parser.add_argument('--start', type=pd.Timestamp, default=DEFAULT_START)
        arguments = parser.parse_args()
        source = bhavcopy_price_source.BhavcopyPriceSource(
            DATA_DIRECTORY / 'bhavcopy' / 'store',
            DATA_DIRECTORY / 'bhavcopy' / 'corporate_actions',
        )
        daily_panel = source.daily_panel()
        in_sample = (daily_panel['date'] >= arguments.start) & (daily_panel['date'] <= LAST_COMPLETE_DAY)
        daily_panel = implausible_move_filter.ImplausibleMoveFilter().clean(daily_panel[in_sample])
        panel = monthly_return_panel.MonthlyReturnPanel(daily_panel)
        benchmark = benchmark_history.BenchmarkHistory(DATA_DIRECTORY).monthly_returns(total_return=True)
        comparison = portfolio_comparison.PortfolioComparison(panel, benchmark, 'NIFTY 500 total return')
        table = comparison.table()
        OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
        table.to_csv(OUTPUT_DIRECTORY / f'bhavcopy_from_{arguments.start.year}.csv')
        comparison.net_returns().to_csv(OUTPUT_DIRECTORY / f'bhavcopy_from_{arguments.start.year}_monthly_net_returns.csv')
        print(f'{len(table)} portfolios, {table["months"].iloc[0]} months from {table["first_month"].iloc[0]} to {table["last_month"].iloc[0]}; NIFTY 500 total return compound annual {table["benchmark_compound_annual"].iloc[0]:.2%}')
        print(table[SHOWN_COLUMNS].round(3).to_string())


if __name__ == '__main__':
    ComparePortfoliosApplication().run()
