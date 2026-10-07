"""Removes one-day returns too large to be real trading, which are usually unadjusted splits or bonuses.

Typical usage example:

  move_filter = ImplausibleMoveFilter()
  cleaned_panel = move_filter.clean(daily_panel)
  print(move_filter.removed_rows)
"""

import pandas as pd


class ImplausibleMoveFilter:
    """A rule that sets implausibly large one-day returns to zero and remembers which rows it changed.

    Attributes:
        lowest_return: The float one-day return below which a move is treated as a data error.
        highest_return: The float one-day return above which a move is treated as a data error.
        removed_rows: A pandas.DataFrame of the rows whose return was set to zero by the last call to clean, or None before the first call.
    """

    def __init__(self, lowest_return: float = -0.5, highest_return: float = 1.0):
        """Initialises the filter.

        Args:
            lowest_return: The float one-day return below which a move is treated as a data error.
            highest_return: The float one-day return above which a move is treated as a data error.

        Raises:
            ValueError: lowest_return is not below highest_return.
        """
        if lowest_return >= highest_return:
            raise ValueError(f'Bounds are the wrong way round: {lowest_return=} {highest_return=}')
        self.lowest_return = lowest_return
        self.highest_return = highest_return
        self.removed_rows = None

    def clean(self, daily_panel: pd.DataFrame) -> pd.DataFrame:
        """Returns a copy of the panel with implausible daily returns set to zero.

        Args:
            daily_panel: A pandas.DataFrame with at least `symbol`, `date` and `daily_return` columns.

        Returns:
            A pandas.DataFrame like daily_panel, in which each implausible `daily_return` is 0.0.

        Raises:
            KeyError: daily_panel has no `daily_return` column.
        """
        too_low = daily_panel['daily_return'] < self.lowest_return
        too_high = daily_panel['daily_return'] > self.highest_return
        implausible = too_low | too_high
        self.removed_rows = daily_panel[implausible].copy()
        cleaned_panel = daily_panel.copy()
        cleaned_panel.loc[implausible, 'daily_return'] = 0.0
        return cleaned_panel
