"""Compares the 64 long-only winners portfolios as an investor would hold them, after Indian trading costs.

Each portfolio is scored over the months all 64 share, on compound annual return, return above the NIFTY 500, volatility, Sharpe ratio, maximum drawdown and turnover, and on whether it beat the index in both halves of the sample, because the best of 64 backtests is partly luck.

Typical usage example:

  comparison = PortfolioComparison(panel, market_returns)
  table = comparison.table()
"""

import numpy as np
import pandas as pd

from jegadeesh_titman_india.live import strategy_specification
from jegadeesh_titman_india.momentum import indian_transaction_costs
from jegadeesh_titman_india.momentum import monthly_return_panel
from jegadeesh_titman_india.momentum import overlapping_strategy
from jegadeesh_titman_india.momentum import return_statistics
from jegadeesh_titman_india.momentum import strategy_grid
from jegadeesh_titman_india.momentum import universe_filter


MOST_TRADED_COUNT = 500

IMPACT_COST_BY_UNIVERSE = {
    'all_shares': 0.003,
    'most_traded_500': 0.001,
}


class PortfolioComparison:
    """The scores of every long-only winners portfolio on one sample.

    Attributes:
        panel: The monthly_return_panel.MonthlyReturnPanel of share returns.
        benchmark_returns: A pandas.Series of monthly benchmark returns indexed by month.
        benchmark_name: The str name of the benchmark, used in column names.
    """

    def __init__(
        self,
        panel: monthly_return_panel.MonthlyReturnPanel,
        benchmark_returns: pd.Series,
        benchmark_name: str,
    ):
        """Initialises the comparison.

        Args:
            panel: The monthly_return_panel.MonthlyReturnPanel of share returns.
            benchmark_returns: A pandas.Series of monthly benchmark returns indexed by month.
            benchmark_name: The str name of the benchmark.

        Raises:
            Nothing.
        """
        self.panel = panel
        self.benchmark_returns = benchmark_returns
        self.benchmark_name = benchmark_name
        self._statistics = return_statistics.ReturnStatistics()

    def net_returns(self) -> pd.DataFrame:
        """Gives every portfolio's monthly return after Indian trading costs.

        Returns:
            A pandas.DataFrame indexed by month with one column per strategy name, NaN before a portfolio has a full set of cohorts.

        Raises:
            Nothing.
        """
        grids = {}
        for universe_name in IMPACT_COST_BY_UNIVERSE:
            most_traded_count = MOST_TRADED_COUNT if universe_name == 'most_traded_500' else None
            universe = universe_filter.UniverseFilter(self.panel, most_traded_count=most_traded_count)
            grids[universe_name] = strategy_grid.StrategyGrid(self.panel, universe)
        columns = {}
        for specification in strategy_specification.StrategySpecification.all_specifications():
            strategy = grids[specification.universe_name].build(
                specification.ranking_months,
                specification.holding_months,
                specification.skipped_days,
            )
            gross = strategy.decile_returns()[overlapping_strategy.WINNERS]
            bought, sold = strategy.turnover(overlapping_strategy.WINNERS)
            costs = indian_transaction_costs.IndianTransactionCosts(impact_cost=IMPACT_COST_BY_UNIVERSE[specification.universe_name])
            columns[specification.name] = costs.net_returns(gross, bought, sold).where(gross.notna())
            columns[specification.name + '__turnover'] = (bought + sold).where(gross.notna())
        return pd.DataFrame(columns)

    def table(self) -> pd.DataFrame:
        """Scores every portfolio over the months all of them share.

        Returns:
            A pandas.DataFrame indexed by strategy name, sorted by return above the benchmark, with `universe`, `ranking_months`, `holding_months`, `skipped_days`, `compound_annual`, `benchmark_compound_annual`, `excess_annual`, `excess_t`, `volatility_annual`, `sharpe`, `maximum_drawdown`, `worst_month`, `months_beating_benchmark`, `excess_first_half`, `excess_second_half`, `annual_turnover` and `months` columns.

        Raises:
            Nothing.
        """
        frame = self.net_returns()
        return_columns = []
        for column in frame.columns:
            if not column.endswith('__turnover'):
                return_columns.append(column)
        common = frame[return_columns].dropna().index.intersection(self.benchmark_returns.dropna().index)
        benchmark = self.benchmark_returns.loc[common]
        half = len(common) // 2
        rows = []
        for specification in strategy_specification.StrategySpecification.all_specifications():
            returns = frame.loc[common, specification.name]
            excess = returns - benchmark
            wealth = (1.0 + returns).cumprod()
            drawdown = wealth / wealth.cummax() - 1.0
            excess_mean, excess_t = self._statistics.mean_and_t(excess)
            rows.append(
                {
                    'strategy': specification.name,
                    'universe': specification.universe_name,
                    'ranking_months': specification.ranking_months,
                    'holding_months': specification.holding_months,
                    'skipped_days': specification.skipped_days,
                    'compound_annual': self._compound_annual(returns),
                    'benchmark_compound_annual': self._compound_annual(benchmark),
                    'excess_annual': self._compound_annual(returns) - self._compound_annual(benchmark),
                    'excess_t': excess_t,
                    'volatility_annual': float(returns.std() * np.sqrt(12.0)),
                    'sharpe': float(returns.mean() / returns.std() * np.sqrt(12.0)),
                    'maximum_drawdown': float(drawdown.min()),
                    'worst_month': float(returns.min()),
                    'months_beating_benchmark': float((excess > 0).mean()),
                    'excess_first_half': self._compound_annual(returns.iloc[:half]) - self._compound_annual(benchmark.iloc[:half]),
                    'excess_second_half': self._compound_annual(returns.iloc[half:]) - self._compound_annual(benchmark.iloc[half:]),
                    'annual_turnover': float(frame.loc[common, specification.name + '__turnover'].mean() * 12.0 / 2.0),
                    'months': len(common),
                    'first_month': str(common.min()),
                    'last_month': str(common.max()),
                }
            )
        table = pd.DataFrame(rows).set_index('strategy')
        return table.sort_values('excess_annual', ascending=False)

    def _compound_annual(self, returns: pd.Series) -> float:
        """Gives the compound annual growth rate of a monthly return series.

        Args:
            returns: A pandas.Series of monthly returns without gaps.

        Returns:
            The float compound annual return, NaN for an empty series.

        Raises:
            Nothing.
        """
        if len(returns) == 0:
            return float('nan')
        return float((1.0 + returns).prod() ** (12.0 / len(returns)) - 1.0)
