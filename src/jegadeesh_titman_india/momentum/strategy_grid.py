"""Builds the paper's J-month/K-month strategies and summarises all of them, as in the paper's Table I.

Typical usage example:

  grid = StrategyGrid(panel, universe)
  table = grid.table_one()
  six_six = grid.build(ranking_months=6, holding_months=6, skipped_days=0)
"""

import pandas as pd

from jegadeesh_titman_india.momentum import decile_ranker
from jegadeesh_titman_india.momentum import monthly_return_panel
from jegadeesh_titman_india.momentum import overlapping_strategy
from jegadeesh_titman_india.momentum import return_statistics
from jegadeesh_titman_india.momentum import universe_filter


RANKING_MONTHS = [
    3,
    6,
    9,
    12,
]

HOLDING_MONTHS = [
    3,
    6,
    9,
    12,
]

SKIPPED_DAYS = [
    0,
    5,
]


class StrategyGrid:
    """The 32 strategies of the paper's Table I, run on one universe of shares.

    Attributes:
        panel: The monthly_return_panel.MonthlyReturnPanel of share returns.
        universe: The universe_filter.UniverseFilter deciding which shares are ranked.
    """

    def __init__(
        self,
        panel: monthly_return_panel.MonthlyReturnPanel,
        universe: universe_filter.UniverseFilter,
    ):
        """Initialises the grid.

        Args:
            panel: The monthly_return_panel.MonthlyReturnPanel of share returns.
            universe: The universe_filter.UniverseFilter deciding which shares are ranked.

        Raises:
            Nothing.
        """
        self.panel = panel
        self.universe = universe
        self._ranker = decile_ranker.DecileRanker()
        self._statistics = return_statistics.ReturnStatistics()

    def build(
        self,
        ranking_months: int,
        holding_months: int,
        skipped_days: int,
        group: pd.DataFrame | None = None,
    ) -> overlapping_strategy.OverlappingStrategy:
        """Builds one strategy, optionally ranking only within one group of shares.

        Args:
            ranking_months: The int number of months, J in the paper, in the ranking period.
            holding_months: The int number of months, K in the paper, each cohort is held.
            skipped_days: The int number of trading days between the ranking period and the holding period, 0 or 5 in this study.
            group: A pandas.DataFrame of bools, months by symbols, True for shares in the group to rank within, or None to rank the whole universe.

        Returns:
            The overlapping_strategy.OverlappingStrategy.

        Raises:
            ValueError: A month count is less than 1 or skipped_days is negative.
        """
        eligible = self.universe.eligible(ranking_months)
        if group is not None:
            eligible = eligible & group.fillna(False).astype(bool)
        ranking_returns = self.panel.ranking_returns(ranking_months, skipped_days)
        deciles = self._ranker.assign(ranking_returns, eligible)
        return overlapping_strategy.OverlappingStrategy(self.panel.monthly_returns, deciles, holding_months)

    def table_one(self) -> pd.DataFrame:
        """Runs all 32 strategies over the months they all share and summarises them.

        Returns:
            A pandas.DataFrame with one row per strategy and portfolio, and columns `ranking_months`, `holding_months`, `skipped_days`, `portfolio` (`sell`, `buy` or `buy_minus_sell`), `mean`, `t_statistic`, `months`, `first_month` and `last_month`.

        Raises:
            Nothing.
        """
        series_by_strategy = {}
        for skipped_days in SKIPPED_DAYS:
            for ranking_months in RANKING_MONTHS:
                for holding_months in HOLDING_MONTHS:
                    strategy = self.build(ranking_months, holding_months, skipped_days)
                    returns = strategy.decile_returns()
                    key = (ranking_months, holding_months, skipped_days)
                    series_by_strategy[key] = returns
        common_months = None
        for returns in series_by_strategy.values():
            months = returns['winners_minus_losers'].dropna().index
            if common_months is None:
                common_months = months
            else:
                common_months = common_months.intersection(months)
        rows = []
        for key, returns in series_by_strategy.items():
            ranking_months, holding_months, skipped_days = key
            portfolios = {
                'sell': returns[overlapping_strategy.LOSERS],
                'buy': returns[overlapping_strategy.WINNERS],
                'buy_minus_sell': returns['winners_minus_losers'],
            }
            for portfolio, series in portfolios.items():
                mean, t_statistic = self._statistics.mean_and_t(series.loc[common_months])
                rows.append(
                    {
                        'ranking_months': ranking_months,
                        'holding_months': holding_months,
                        'skipped_days': skipped_days,
                        'portfolio': portfolio,
                        'mean': mean,
                        't_statistic': t_statistic,
                        'months': len(common_months),
                        'first_month': str(common_months.min()),
                        'last_month': str(common_months.max()),
                    }
                )
        return pd.DataFrame(rows)
