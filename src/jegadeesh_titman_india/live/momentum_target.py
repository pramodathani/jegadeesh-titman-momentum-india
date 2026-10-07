"""Works out what one strategy should hold next month and turns it into a tradingmachine Index.

The target is the winners decile of the K most recent cohorts, formed exactly as in the backtest, each cohort carrying 1/K of the money and its shares equally weighted within it.

Typical usage example:

  target = MomentumTarget(panel, specification)
  weights = target.weights()
  target_index = target.to_index()
"""

import pandas as pd

from tradingmachine.asset_baskets import index
from tradingmachine.asset_baskets import member_resolver

from jegadeesh_titman_india.live import strategy_specification
from jegadeesh_titman_india.momentum import monthly_return_panel
from jegadeesh_titman_india.momentum import overlapping_strategy
from jegadeesh_titman_india.momentum import strategy_grid
from jegadeesh_titman_india.momentum import universe_filter


MOST_TRADED_COUNT = 500


class MomentumTarget:
    """The weights one strategy should hold in the month after the data ends.

    Attributes:
        panel: The monthly_return_panel.MonthlyReturnPanel the ranking is done on.
        specification: The strategy_specification.StrategySpecification being targeted.
    """

    def __init__(
        self,
        panel: monthly_return_panel.MonthlyReturnPanel,
        specification: strategy_specification.StrategySpecification,
    ):
        """Initialises the target.

        Args:
            panel: The monthly_return_panel.MonthlyReturnPanel the ranking is done on.
            specification: The strategy_specification.StrategySpecification being targeted.

        Raises:
            Nothing.
        """
        self.panel = panel
        self.specification = specification
        self._weights = None

    @property
    def formation_month(self) -> pd.Period:
        """The pandas.Period of the last month of data, whose end is the latest formation date."""
        return self.panel.months[-1]

    def weights(self) -> pd.Series:
        """Gives the target weight of every share to hold next month.

        Returns:
            A pandas.Series of weights indexed by NSE symbol, summing to 1, largest first.

        Raises:
            ValueError: The data does not reach back far enough to form K cohorts.
        """
        if self._weights is None:
            most_traded_count = None
            if self.specification.universe_name == 'most_traded_500':
                most_traded_count = MOST_TRADED_COUNT
            universe = universe_filter.UniverseFilter(self.panel, most_traded_count=most_traded_count)
            grid = strategy_grid.StrategyGrid(self.panel, universe)
            strategy = grid.build(
                self.specification.ranking_months,
                self.specification.holding_months,
                self.specification.skipped_days,
            )
            weights = strategy.next_month_weights(overlapping_strategy.WINNERS)
            self._weights = weights.sort_values(ascending=False)
        return self._weights

    def to_index(self, resolver: member_resolver.MemberResolver | None = None) -> index.Index:
        """Builds a tradingmachine Index with the target weights, looking every share up in UBI in one request.

        Args:
            resolver: The tradingmachine MemberResolver to look the shares up with, or None to make one on the shared client.

        Returns:
            A tradingmachine.asset_baskets.index.Index named after the strategy, weighted by the stated target weights.

        Raises:
            BasketMemberError: UBI could not find one or more of the shares.
            UnifiedBrokerInterfaceError: UBI refused the request or could not be reached.
        """
        if resolver is None:
            resolver = member_resolver.MemberResolver()
        rows = []
        for symbol, weight in self.weights().items():
            rows.append(
                {
                    'exchange': 'nse',
                    'segment': 'equities',
                    'symbol': symbol,
                    'weight': float(weight),
                }
            )
        members = resolver.resolve(rows)
        return index.Index(
            name=self.specification.name,
            members=members,
            weighting=index.STATED_WEIGHTING,
            unified_broker_interface=resolver.unified_broker_interface,
        )
