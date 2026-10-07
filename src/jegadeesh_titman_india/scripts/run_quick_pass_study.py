"""Runs the momentum study on tradingmachine's prices, the quick pass from December 2019.

These prices cover only shares listed today and are not adjusted for dividends, so the results are biased upwards and are kept as a cross-check of the bhavcopy study. This needs the optional `live` dependencies and a running Unified Broker Interface for fetch_tradingmachine_prices.

Run from the repository root after fetch_tradingmachine_prices:

  python -m jegadeesh_titman_india.scripts.run_quick_pass_study

Tables are written under `results/tradingmachine/`.
"""

import logging
import pathlib

import pandas as pd

from jegadeesh_titman_india.momentum import momentum_study
from jegadeesh_titman_india.momentum.price_sources import tradingmachine_price_source


STUDY_DIRECTORY = pathlib.Path(__file__).resolve().parents[3]

DATA_DIRECTORY = STUDY_DIRECTORY / 'data'

RESULTS_DIRECTORY = STUDY_DIRECTORY / 'results'

LAST_COMPLETE_DAY = pd.Timestamp('2026-09-30')


class RunQuickPassStudyApplication:
    """The command-line program that runs the study on the tradingmachine prices."""

    def run(self) -> None:
        """Loads the cached prices and index closes and runs the study.

        Returns:
            None.

        Raises:
            FileNotFoundError: The tradingmachine cache has not been filled.
        """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        source = tradingmachine_price_source.TradingmachinePriceSource(DATA_DIRECTORY / 'tradingmachine')
        daily_panel = source.daily_panel()
        daily_panel = daily_panel[daily_panel['date'] <= LAST_COMPLETE_DAY]
        closes = source.index_closes()
        closes = closes[closes.index <= LAST_COMPLETE_DAY]
        benchmark_returns = closes.groupby(closes.index.to_period('M')).last().pct_change()
        study = momentum_study.MomentumStudy(
            output_directory=RESULTS_DIRECTORY / 'tradingmachine',
            title='Momentum on NSE shares, quick pass on tradingmachine prices (survivors only, price returns)',
            daily_panel=daily_panel,
            benchmark_returns=benchmark_returns,
            benchmark_description='NIFTY 500 and Nifty500 Equal Weight price returns, without dividends',
        )
        study.run()


if __name__ == '__main__':
    RunQuickPassStudyApplication().run()
