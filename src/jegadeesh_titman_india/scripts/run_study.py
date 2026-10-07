"""Runs the momentum study on NSE bhavcopy data, which includes delisted shares and dividends.

The main sample starts in 2005, the first year NSE's corporate action list is complete. The benchmark is the NIFTY 500 with its dividend yield added, from NSE's daily index files from July 2012 and, when present, the tradingmachine index cache before that.

Run from the repository root after download_bhavcopy, build_bhavcopy_store and download_index_history:

  python -m jegadeesh_titman_india.scripts.run_study
  python -m jegadeesh_titman_india.scripts.run_study --start 1995-01-01

Tables are written under `results/bhavcopy_from_<year>/`.
"""

import argparse
import logging
import pathlib

import pandas as pd

from jegadeesh_titman_india.momentum import benchmark_history
from jegadeesh_titman_india.momentum import momentum_study
from jegadeesh_titman_india.momentum.price_sources import bhavcopy_price_source


STUDY_DIRECTORY = pathlib.Path(__file__).resolve().parents[3]

DATA_DIRECTORY = STUDY_DIRECTORY / 'data'

RESULTS_DIRECTORY = STUDY_DIRECTORY / 'results'

LAST_COMPLETE_DAY = pd.Timestamp('2026-09-30')

DEFAULT_START = pd.Timestamp('2005-01-01')


class RunStudyApplication:
    """The command-line program that runs the study on the bhavcopy data."""

    def run(self) -> None:
        """Reads the command line, loads the data and benchmark, and runs the study.

        Returns:
            None.

        Raises:
            FileNotFoundError: The bhavcopy store or the index history has not been built.
        """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        parser = argparse.ArgumentParser(description='Run the momentum study on NSE bhavcopy data.')
        parser.add_argument('--start', type=pd.Timestamp, default=DEFAULT_START)
        arguments = parser.parse_args()
        source = bhavcopy_price_source.BhavcopyPriceSource(
            DATA_DIRECTORY / 'bhavcopy' / 'store',
            DATA_DIRECTORY / 'bhavcopy' / 'corporate_actions',
        )
        daily_panel = source.daily_panel()
        in_sample = (daily_panel['date'] >= arguments.start) & (daily_panel['date'] <= LAST_COMPLETE_DAY)
        daily_panel = daily_panel[in_sample]
        benchmark = benchmark_history.BenchmarkHistory(DATA_DIRECTORY).monthly_returns(total_return=True)
        study = momentum_study.MomentumStudy(
            output_directory=RESULTS_DIRECTORY / f'bhavcopy_from_{arguments.start.year}',
            title='Momentum on NSE shares, bhavcopy data with corporate actions and dividends',
            daily_panel=daily_panel,
            benchmark_returns=benchmark.to_frame(),
            benchmark_description='NIFTY 500 approximate total return: price return plus one twelfth of the month\'s average dividend yield',
            adjustment_report=source.adjustment_report,
            include_subperiods=True,
        )
        study.run()


if __name__ == '__main__':
    RunStudyApplication().run()
