"""Decides which shares may be ranked at each formation month.

The paper ranks every stock with returns over the whole ranking period. Indian microcaps are often too illiquid to trade, so the filter can also keep only the most traded shares, as a stand-in for the Nifty 500 because market capitalisation is not available.

Typical usage example:

  universe = UniverseFilter(panel, most_traded_count=500)
  eligible = universe.eligible(ranking_months=6)
"""

import pandas as pd

from jegadeesh_titman_india.momentum import monthly_return_panel


class UniverseFilter:
    """The rule for which shares are eligible to be ranked in each month.

    Attributes:
        panel: The monthly_return_panel.MonthlyReturnPanel the shares come from.
        most_traded_count: The int number of most-traded eligible shares to keep, or None to keep every eligible share.
        liquidity_months: The int number of months over which traded value is averaged when choosing the most-traded shares.
    """

    def __init__(
        self,
        panel: monthly_return_panel.MonthlyReturnPanel,
        most_traded_count: int | None = None,
        liquidity_months: int = 6,
    ):
        """Initialises the filter.

        Args:
            panel: The monthly_return_panel.MonthlyReturnPanel the shares come from.
            most_traded_count: The int number of most-traded shares to keep, or None to keep every eligible share.
            liquidity_months: The int number of months over which traded value is averaged.

        Raises:
            ValueError: most_traded_count is given and is less than 10, too few to form deciles.
        """
        if most_traded_count is not None and most_traded_count < 10:
            raise ValueError(f'Too few shares to form deciles: {most_traded_count=}')
        self.panel = panel
        self.most_traded_count = most_traded_count
        self.liquidity_months = liquidity_months

    def eligible(self, ranking_months: int) -> pd.DataFrame:
        """Marks the shares that may be ranked at the end of each month.

        A share must have traded in the formation month and in each of the ranking_months months before it, so that its ranking return starts from a real price.

        Args:
            ranking_months: The int number of months, J in the paper, in the ranking period.

        Returns:
            A pandas.DataFrame of bools, months by symbols.

        Raises:
            ValueError: ranking_months is less than 1.
        """
        eligible = self.panel.traded_in_every_month(ranking_months + 1)
        if self.most_traded_count is None:
            return eligible
        traded_value = self.panel.trailing_traded_value(self.liquidity_months).where(eligible)
        traded_value_rank = traded_value.rank(axis=1, ascending=False, method='first')
        return eligible & (traded_value_rank <= self.most_traded_count)

    def liquidity_terciles(self, ranking_months: int) -> pd.DataFrame:
        """Splits the eligible shares in each month into three groups by traded value.

        These groups stand in for the paper's small, medium and large size groups, because market capitalisation is not available.

        Args:
            ranking_months: The int number of months, J in the paper, in the ranking period.

        Returns:
            A pandas.DataFrame of floats, months by symbols, holding 1 for the least traded third, 2 for the middle third, 3 for the most traded third, and NaN for shares that are not eligible.

        Raises:
            ValueError: ranking_months is less than 1.
        """
        eligible = self.eligible(ranking_months)
        traded_value = self.panel.trailing_traded_value(self.liquidity_months).where(eligible)
        percentile = traded_value.rank(axis=1, pct=True)
        terciles = pd.DataFrame(index=percentile.index, columns=percentile.columns, dtype=float)
        terciles[percentile <= 1.0 / 3.0] = 1.0
        terciles[(percentile > 1.0 / 3.0) & (percentile <= 2.0 / 3.0)] = 2.0
        terciles[percentile > 2.0 / 3.0] = 3.0
        return terciles
