"""Builds the monthly return panel used for live targets from the cached tradingmachine prices, and checks they are fresh.

Live targets must be formed on the month that has just ended. Shares listed today are exactly the ones that can be bought, so the survivorship bias that matters for the backtest does not matter here.

Typical usage example:

  panel = LivePanel(cache_directory).build()
"""

import datetime
import logging
import pathlib

import pandas as pd

from jegadeesh_titman_india.momentum import implausible_move_filter
from jegadeesh_titman_india.momentum import monthly_return_panel
from jegadeesh_titman_india.momentum.price_sources import tradingmachine_price_source


class StalePricesError(RuntimeError):
    """The cached prices do not reach the end of the month that has just finished."""


class LivePanel:
    """The monthly panel for forming next month's live targets.

    Attributes:
        cache_directory: The pathlib.Path of the tradingmachine price cache.
        today: The datetime.date treated as today.
    """

    def __init__(self, cache_directory: pathlib.Path, today: datetime.date | None = None):
        """Initialises the panel builder.

        Args:
            cache_directory: The pathlib.Path of the tradingmachine price cache.
            today: The datetime.date treated as today, or None for the real date.

        Raises:
            Nothing.
        """
        self.cache_directory = cache_directory
        self.today = today if today is not None else datetime.date.today()

    @property
    def last_finished_month(self) -> pd.Period:
        """The pandas.Period of the calendar month before today's."""
        return pd.Period(self.today, freq='M') - 1

    def build(self) -> monthly_return_panel.MonthlyReturnPanel:
        """Reads the cache, keeps complete months only, removes implausible moves and builds the panel.

        Returns:
            The monthly_return_panel.MonthlyReturnPanel whose last month is the month that has just finished.

        Raises:
            StalePricesError: The cache does not reach the last week of the month that has just finished.
            FileNotFoundError: The cache has not been filled.
        """
        source = tradingmachine_price_source.TradingmachinePriceSource(self.cache_directory)
        daily_panel = source.daily_panel()
        month_end = self.last_finished_month.end_time.normalize()
        daily_panel = daily_panel[daily_panel['date'] <= month_end]
        latest_day = daily_panel['date'].max()
        if latest_day < month_end - pd.Timedelta(days=7):
            raise StalePricesError(f'Prices end on {latest_day.date()}, before the end of {self.last_finished_month}; run fetch_tradingmachine_prices first')
        move_filter = implausible_move_filter.ImplausibleMoveFilter()
        cleaned = move_filter.clean(daily_panel)
        logging.info('Set %s implausible daily returns to zero', len(move_filter.removed_rows))
        return monthly_return_panel.MonthlyReturnPanel(cleaned)
