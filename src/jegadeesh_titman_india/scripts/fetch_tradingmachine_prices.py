"""Fetches daily NSE share and index prices from tradingmachine and caches them for the study.

Run from the repository root, with UBI running. By default prices are fetched up to the last day of the previous calendar month, which is what live targets are formed on:

  python -m jegadeesh_titman_india.scripts.fetch_tradingmachine_prices
  python -m jegadeesh_titman_india.scripts.fetch_tradingmachine_prices --last-date 2026-09-30
"""

import argparse
import datetime
import logging
import pathlib

from jegadeesh_titman_india.momentum.price_sources import tradingmachine_price_source


STUDY_DIRECTORY = pathlib.Path(__file__).resolve().parents[3]

CACHE_DIRECTORY = STUDY_DIRECTORY / 'data' / 'tradingmachine'


class FetchTradingmachinePricesApplication:
    """The command-line program that fills the tradingmachine price cache."""

    def run(self) -> None:
        """Fetches and caches the prices.

        Returns:
            None.

        Raises:
            UnifiedBrokerInterfaceError: UBI refused a request or could not be reached.
        """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        first_of_this_month = datetime.date.today().replace(day=1)
        last_of_previous_month = first_of_this_month - datetime.timedelta(days=1)
        parser = argparse.ArgumentParser(description='Fetch and cache NSE prices from tradingmachine.')
        parser.add_argument('--last-date', type=datetime.date.fromisoformat, default=last_of_previous_month)
        arguments = parser.parse_args()
        source = tradingmachine_price_source.TradingmachinePriceSource(
            cache_directory=CACHE_DIRECTORY,
            last_date=arguments.last_date.isoformat(),
        )
        source.fetch_and_cache()


if __name__ == '__main__':
    FetchTradingmachinePricesApplication().run()
