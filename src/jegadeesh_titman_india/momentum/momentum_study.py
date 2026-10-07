"""One complete run of the Jegadeesh and Titman (1993) study on a set of daily Indian share returns.

The study builds monthly returns, runs all 32 of the paper's strategies on all shares and on the 500 most traded, and writes the paper's tables as CSV files plus a readable `summary.md`: Table I (all strategies), Tables II and III (decile risk, liquidity groups), Tables IV and V (calendar months), Table VI (five-year subperiods, for long samples) and Table VII (event time), along with a comparison of the long-short spread and the long-only winners portfolio after Indian costs.

Typical usage example:

  study = MomentumStudy(output_directory, 'Momentum on NSE shares', daily_panel, benchmark_returns, 'NIFTY 500 total return')
  study.run()
"""

import logging
import pathlib

import numpy as np
import pandas as pd

from jegadeesh_titman_india.momentum import calendar_month_study
from jegadeesh_titman_india.momentum import event_time_study
from jegadeesh_titman_india.momentum import implausible_move_filter
from jegadeesh_titman_india.momentum import indian_transaction_costs
from jegadeesh_titman_india.momentum import markdown_table
from jegadeesh_titman_india.momentum import monthly_return_panel
from jegadeesh_titman_india.momentum import overlapping_strategy
from jegadeesh_titman_india.momentum import return_statistics
from jegadeesh_titman_india.momentum import strategy_grid
from jegadeesh_titman_india.momentum import universe_filter


MOST_TRADED_COUNT = 500

PAPER_ONE_WAY_COST = 0.005

IMPACT_COST_BY_UNIVERSE = {
    'all_shares': 0.003,
    'most_traded_500': 0.001,
}

MARKET_INDEX = 'NIFTY 500'

EQUAL_WEIGHTED_INDEX = 'Nifty500 EW'

FEATURED_RANKING_MONTHS = 6

FEATURED_HOLDING_MONTHS = 6

EVENT_HORIZON_MONTHS = 36


class MomentumStudy:
    """One complete run of the study on one set of daily share returns.

    Attributes:
        output_directory: The pathlib.Path the tables are written to.
        title: The str heading of the summary, naming the data used.
        daily_panel: The pandas.DataFrame of daily share rows with `date`, `symbol`, `daily_return` and `traded_value` columns.
        benchmark_returns: A pandas.DataFrame of monthly benchmark returns indexed by month, with a `NIFTY 500` column and optionally a `Nifty500 EW` column.
        benchmark_description: The str description of the benchmark returns, such as whether they include dividends.
        adjustment_report: A dict describing the corporate actions applied to the prices, or None.
        include_subperiods: A bool that is True to add the five-year subperiod table, which needs a long sample.
    """

    def __init__(
        self,
        output_directory: pathlib.Path,
        title: str,
        daily_panel: pd.DataFrame,
        benchmark_returns: pd.DataFrame,
        benchmark_description: str,
        adjustment_report: dict | None = None,
        include_subperiods: bool = False,
    ):
        """Initialises the study.

        Args:
            output_directory: The pathlib.Path the tables are written to.
            title: The str heading of the summary, naming the data used.
            daily_panel: The pandas.DataFrame of daily share rows.
            benchmark_returns: A pandas.DataFrame of monthly benchmark returns with a `NIFTY 500` column.
            benchmark_description: The str description of the benchmark returns.
            adjustment_report: A dict describing the corporate actions applied, or None.
            include_subperiods: A bool that is True to add the five-year subperiod table.

        Raises:
            KeyError: benchmark_returns has no `NIFTY 500` column.
        """
        if MARKET_INDEX not in benchmark_returns.columns:
            raise KeyError(f'benchmark_returns needs a {MARKET_INDEX!r} column')
        self.output_directory = output_directory
        self.title = title
        self.daily_panel = daily_panel
        self.benchmark_returns = benchmark_returns
        self.benchmark_description = benchmark_description
        self.adjustment_report = adjustment_report
        self.include_subperiods = include_subperiods
        self._statistics = return_statistics.ReturnStatistics()
        self._summary_parts = []

    def run(self) -> None:
        """Builds the panel, runs every table and writes the results.

        Returns:
            None.

        Raises:
            OSError: A result file cannot be written.
        """
        self.output_directory.mkdir(parents=True, exist_ok=True)
        panel = self._build_panel()
        market_returns = pd.concat(
            [
                self.benchmark_returns,
                panel.equal_weighted_market_returns().rename('equal_weighted_all_shares'),
            ],
            axis=1,
        )
        universes = {
            'all_shares': universe_filter.UniverseFilter(panel),
            'most_traded_500': universe_filter.UniverseFilter(panel, most_traded_count=MOST_TRADED_COUNT),
        }
        for universe_name, universe in universes.items():
            logging.info('Running universe %s', universe_name)
            self._run_universe(universe_name, panel, universe, market_returns)
        summary_path = self.output_directory / 'summary.md'
        summary_path.write_text('\n\n'.join(self._summary_parts) + '\n')
        logging.info('Wrote %s', summary_path)

    def _build_panel(self) -> monthly_return_panel.MonthlyReturnPanel:
        """Removes implausible moves from the daily rows and builds the monthly panel.

        Returns:
            The monthly_return_panel.MonthlyReturnPanel.

        Raises:
            OSError: The list of removed moves cannot be written.
        """
        daily_panel = self.daily_panel
        move_filter = implausible_move_filter.ImplausibleMoveFilter()
        daily_panel = move_filter.clean(daily_panel)
        removed = move_filter.removed_rows
        removed.to_csv(self.output_directory / 'implausible_moves_removed.csv', index=False)
        panel = monthly_return_panel.MonthlyReturnPanel(daily_panel)
        self._summary_parts.append(
            '\n'.join(
                [
                    f'# {self.title}',
                    '',
                    f'Daily rows: {len(daily_panel):,}. Shares: {daily_panel["symbol"].nunique():,}. Dates: {daily_panel["date"].min().date()} to {daily_panel["date"].max().date()}.',
                    f'Daily returns below -50% or above +100% set to zero as data errors: {len(removed):,} rows in {removed["symbol"].nunique():,} shares.',
                    f'Corporate actions: {self.adjustment_report}.',
                    f'Benchmark: {self.benchmark_description}.',
                    '',
                    '### Data quality by year',
                    '',
                    markdown_table.MarkdownTable(self._data_quality_by_year(daily_panel, removed)).render(),
                ]
            )
        )
        return panel

    def _data_quality_by_year(self, daily_panel: pd.DataFrame, removed: pd.DataFrame) -> pd.DataFrame:
        """Counts, for each year, the shares traded and the suspiciously large one-day moves left after corporate actions.

        Many unexplained falls of 25 to 50 percent, or many removed data errors, mean splits or bonuses are missing from the corporate action list that year.

        Args:
            daily_panel: The pandas.DataFrame of daily rows after implausible moves were set to zero.
            removed: The pandas.DataFrame of rows whose return was set to zero.

        Returns:
            A pandas.DataFrame indexed by year with `shares`, `share_days`, `falls_25_to_50_percent`, `data_errors_removed` and `suspicious_per_10000_share_days` columns.

        Raises:
            Nothing.
        """
        year = daily_panel['date'].dt.year
        falls = (daily_panel['daily_return'] < -0.25) & (daily_panel['daily_return'] >= -0.5)
        table = pd.DataFrame(
            {
                'shares': daily_panel.groupby(year)['symbol'].nunique(),
                'share_days': daily_panel.groupby(year).size(),
                'falls_25_to_50_percent': falls.groupby(year).sum(),
                'data_errors_removed': removed.groupby(removed['date'].dt.year).size(),
            }
        ).fillna(0).astype(int)
        suspicious = table['falls_25_to_50_percent'] + table['data_errors_removed']
        table['suspicious_per_10000_share_days'] = suspicious / table['share_days'] * 10000.0
        table.index.name = 'year'
        return table

    def _run_universe(
        self,
        universe_name: str,
        panel: monthly_return_panel.MonthlyReturnPanel,
        universe: universe_filter.UniverseFilter,
        market_returns: pd.DataFrame,
    ) -> None:
        """Runs every table for one universe of shares and adds them to the summary.

        Args:
            universe_name: The str name of the universe, used in file names.
            panel: The monthly_return_panel.MonthlyReturnPanel of share returns.
            universe: The universe_filter.UniverseFilter for this universe.
            market_returns: A pandas.DataFrame of monthly benchmark returns, one column per benchmark.

        Returns:
            None.

        Raises:
            Nothing.
        """
        grid = strategy_grid.StrategyGrid(panel, universe)
        table_one = grid.table_one()
        table_one.to_csv(self.output_directory / f'{universe_name}_table_1_all_strategies.csv', index=False)
        self._summary_parts.append(f'## Universe: {universe_name}')
        self._summary_parts.append(self._format_table_one(table_one))
        featured = grid.build(FEATURED_RANKING_MONTHS, FEATURED_HOLDING_MONTHS, skipped_days=0)
        decile_returns = featured.decile_returns()
        decile_returns.to_csv(self.output_directory / f'{universe_name}_six_six_monthly_decile_returns.csv')
        self._summary_parts.append(self._decile_risk_table(universe_name, decile_returns, market_returns, panel, featured))
        self._summary_parts.append(self._tradable_table(universe_name, decile_returns, market_returns, featured))
        self._summary_parts.append(self._liquidity_tercile_table(universe_name, grid, universe, market_returns))
        calendar_table = calendar_month_study.CalendarMonthStudy().table(decile_returns['winners_minus_losers'])
        calendar_table.to_csv(self.output_directory / f'{universe_name}_table_4_calendar_months.csv')
        self._summary_parts.append(f'### 6/6 winners minus losers by calendar month (Tables IV and V)\n\n{markdown_table.MarkdownTable(calendar_table).render()}')
        event_study = event_time_study.EventTimeStudy(panel.monthly_returns, featured.deciles)
        event_table = event_study.table(EVENT_HORIZON_MONTHS)
        event_table.to_csv(self.output_directory / f'{universe_name}_table_7_event_time.csv')
        self._summary_parts.append(f'### 6-month ranking, winners minus losers in event time (Table VII)\n\n{markdown_table.MarkdownTable(event_table).render()}')
        if self.include_subperiods:
            self._summary_parts.append(self._subperiod_table(decile_returns['winners_minus_losers']))

    def _format_table_one(self, table_one: pd.DataFrame) -> str:
        """Lays out the 32 strategies the way the paper's Table I does.

        Args:
            table_one: The pandas.DataFrame returned by StrategyGrid.table_one.

        Returns:
            A str Markdown section with one table per skip setting, each cell holding the mean monthly return and its t-statistic.

        Raises:
            Nothing.
        """
        lines = [
            f'### All 32 strategies (Table I), {table_one["months"].iloc[0]} common months from {table_one["first_month"].iloc[0]} to {table_one["last_month"].iloc[0]}',
        ]
        panel_names = {
            0: 'Panel A: no gap between ranking and holding',
            5: 'Panel B: one-week (5 trading day) gap',
        }
        for skipped_days, panel_name in panel_names.items():
            subset = table_one[table_one['skipped_days'] == skipped_days].copy()
            subset['cell'] = subset.apply(lambda row: f'{row["mean"]:.4f} ({row["t_statistic"]:.2f})', axis=1)
            wide = subset.pivot_table(
                index=[
                    'ranking_months',
                    'portfolio',
                ],
                columns='holding_months',
                values='cell',
                aggfunc='first',
            )
            wide.columns = [f'K={holding_months}' for holding_months in wide.columns]
            lines.append(f'\n{panel_name}\n\n{markdown_table.MarkdownTable(wide.reset_index(level="portfolio")).render()}')
        return '\n'.join(lines)

    def _decile_risk_table(
        self,
        universe_name: str,
        decile_returns: pd.DataFrame,
        market_returns: pd.DataFrame,
        panel: monthly_return_panel.MonthlyReturnPanel,
        featured: overlapping_strategy.OverlappingStrategy,
    ) -> str:
        """Gives each 6/6 decile's mean return, beta against the Nifty 500 and typical traded value, as in the paper's Table II.

        Args:
            universe_name: The str name of the universe, used in file names.
            decile_returns: The pandas.DataFrame of monthly decile returns of the 6/6 strategy.
            market_returns: A pandas.DataFrame of monthly benchmark returns.
            panel: The monthly_return_panel.MonthlyReturnPanel of share returns.
            featured: The 6/6 overlapping_strategy.OverlappingStrategy.

        Returns:
            A str Markdown section holding the table.

        Raises:
            Nothing.
        """
        traded_value = panel.trailing_traded_value().to_numpy()
        rows = []
        columns = list(range(1, 11))
        columns.append('winners_minus_losers')
        for column in columns:
            mean, t_statistic = self._statistics.mean_and_t(decile_returns[column])
            nifty = self._statistics.market_model(decile_returns[column], market_returns[MARKET_INDEX])
            equal_weighted = self._statistics.market_model(decile_returns[column], market_returns['equal_weighted_all_shares'])
            row = {
                'portfolio': f'P{column}' if column != 'winners_minus_losers' else 'P10-P1',
                'mean': mean,
                't_statistic': t_statistic,
                'beta_nifty_500': nifty['beta'],
                'alpha_nifty_500': nifty['alpha'],
                'alpha_t_nifty_500': nifty['alpha_t'],
                'beta_equal_weighted': equal_weighted['beta'],
            }
            if column != 'winners_minus_losers':
                members = featured.deciles == column
                row['median_daily_traded_value_crore'] = float(np.nanmedian(traded_value[members])) / 1e7
            rows.append(row)
        table = pd.DataFrame(rows).set_index('portfolio')
        table.to_csv(self.output_directory / f'{universe_name}_table_2_decile_risk.csv')
        return f'### 6/6 deciles: returns, betas and liquidity (Tables II and III)\n\nTraded value is in rupees crore (10 million) and stands in for market capitalisation. Alphas are market-model intercepts without a risk-free rate.\n\n{markdown_table.MarkdownTable(table).render()}'

    def _tradable_table(
        self,
        universe_name: str,
        decile_returns: pd.DataFrame,
        market_returns: pd.DataFrame,
        featured: overlapping_strategy.OverlappingStrategy,
    ) -> str:
        """Compares the long-short spread and the long-only winners portfolio before and after costs.

        Args:
            universe_name: The str name of the universe, used in file names and to pick the impact cost.
            decile_returns: The pandas.DataFrame of monthly decile returns of the 6/6 strategy.
            market_returns: A pandas.DataFrame of monthly benchmark returns.
            featured: The 6/6 overlapping_strategy.OverlappingStrategy.

        Returns:
            A str Markdown section holding the table.

        Raises:
            Nothing.
        """
        winners_bought, winners_sold = featured.turnover(overlapping_strategy.WINNERS)
        losers_bought, losers_sold = featured.turnover(overlapping_strategy.LOSERS)
        indian_costs = indian_transaction_costs.IndianTransactionCosts(impact_cost=IMPACT_COST_BY_UNIVERSE[universe_name])
        winners_net = indian_costs.net_returns(decile_returns[overlapping_strategy.WINNERS], winners_bought, winners_sold)
        paper_cost = (winners_bought + winners_sold + losers_bought + losers_sold) * PAPER_ONE_WAY_COST
        spread_after_paper_cost = decile_returns['winners_minus_losers'] - paper_cost
        held_months = decile_returns['winners_minus_losers'].notna()
        series = {
            'winners_minus_losers_gross': decile_returns['winners_minus_losers'],
            'winners_minus_losers_after_paper_0.5pct_cost': spread_after_paper_cost.where(held_months),
            'winners_long_only_gross': decile_returns[overlapping_strategy.WINNERS],
            'winners_long_only_after_indian_costs': winners_net.where(held_months),
            'nifty_500': market_returns[MARKET_INDEX].where(held_months),
            'winners_after_costs_minus_nifty_500': (winners_net - market_returns[MARKET_INDEX]).where(held_months),
            'equal_weighted_all_shares': market_returns['equal_weighted_all_shares'].where(held_months),
            'winners_after_costs_minus_equal_weighted_all_shares': (winners_net - market_returns['equal_weighted_all_shares']).where(held_months),
        }
        if EQUAL_WEIGHTED_INDEX in market_returns.columns:
            series['nifty_500_equal_weight'] = market_returns[EQUAL_WEIGHTED_INDEX].where(held_months)
            series['winners_after_costs_minus_nifty_500_equal_weight'] = (winners_net - market_returns[EQUAL_WEIGHTED_INDEX]).where(held_months)
        rows = []
        for name, returns in series.items():
            mean, t_statistic = self._statistics.mean_and_t(returns)
            present = returns.dropna()
            compound_annual = float('nan')
            if len(present) > 0:
                compound_annual = float((1.0 + present).prod() ** (12.0 / len(present)) - 1.0)
            rows.append(
                {
                    'series': name,
                    'mean_monthly': mean,
                    't_statistic': t_statistic,
                    'compound_annual': compound_annual,
                    'months': len(present),
                }
            )
        table = pd.DataFrame(rows).set_index('series')
        table.to_csv(self.output_directory / f'{universe_name}_tradable_comparison.csv')
        semiannual_turnover = (winners_bought[held_months].mean() + winners_sold[held_months].mean()) / 2.0 * 6.0
        return '\n'.join(
            [
                '### 6/6 long-short spread versus long-only winners, before and after costs',
                '',
                f'Indian delivery cost per side: buy {indian_costs.buy_rate():.4%}, sell {indian_costs.sell_rate():.4%}, of which assumed market impact {indian_costs.impact_cost:.2%}. Winners portfolio one-way turnover per six months: {semiannual_turnover:.1%} (paper: 84.8% for the long-short portfolio).',
                '',
                markdown_table.MarkdownTable(table).render(),
            ]
        )

    def _liquidity_tercile_table(
        self,
        universe_name: str,
        grid: strategy_grid.StrategyGrid,
        universe: universe_filter.UniverseFilter,
        market_returns: pd.DataFrame,
    ) -> str:
        """Runs the 6/6 strategy within each third of the universe by traded value, as in the paper's size subsamples.

        Args:
            universe_name: The str name of the universe, used in file names.
            grid: The strategy_grid.StrategyGrid for this universe.
            universe: The universe_filter.UniverseFilter for this universe.
            market_returns: A pandas.DataFrame of monthly benchmark returns.

        Returns:
            A str Markdown section holding the table.

        Raises:
            Nothing.
        """
        terciles = universe.liquidity_terciles(FEATURED_RANKING_MONTHS)
        rows = []
        tercile_names = {
            1: 'L1 least traded',
            2: 'L2 middle',
            3: 'L3 most traded',
        }
        for tercile, tercile_name in tercile_names.items():
            group = terciles == float(tercile)
            strategy = grid.build(FEATURED_RANKING_MONTHS, FEATURED_HOLDING_MONTHS, skipped_days=0, group=group)
            spread = strategy.decile_returns()['winners_minus_losers']
            mean, t_statistic = self._statistics.mean_and_t(spread)
            nifty = self._statistics.market_model(spread, market_returns[MARKET_INDEX])
            rows.append(
                {
                    'group': tercile_name,
                    'mean': mean,
                    't_statistic': t_statistic,
                    'alpha_nifty_500': nifty['alpha'],
                    'alpha_t': nifty['alpha_t'],
                    'beta': nifty['beta'],
                    'months': int(spread.notna().sum()),
                }
            )
        table = pd.DataFrame(rows).set_index('group')
        table.to_csv(self.output_directory / f'{universe_name}_table_3_liquidity_terciles.csv')
        return f'### 6/6 winners minus losers within traded-value terciles (Table III, size subsamples)\n\n{markdown_table.MarkdownTable(table).render()}'

    def _subperiod_table(self, spread: pd.Series) -> str:
        """Gives the 6/6 spread in five-year subperiods, as in the paper's Table VI.

        Args:
            spread: A pandas.Series of monthly winners-minus-losers returns.

        Returns:
            A str Markdown section holding the table.

        Raises:
            Nothing.
        """
        present = spread.dropna()
        rows = []
        first_year = int(present.index.min().year)
        for start_year in range(first_year, int(present.index.max().year) + 1, 5):
            in_period = present[(present.index.year >= start_year) & (present.index.year < start_year + 5)]
            mean, t_statistic = self._statistics.mean_and_t(in_period)
            march = in_period[in_period.index.month == 3]
            march_mean, march_t = self._statistics.mean_and_t(march)
            rows.append(
                {
                    'years': f'{start_year}-{start_year + 4}',
                    'mean': mean,
                    't_statistic': t_statistic,
                    'march_mean': march_mean,
                    'march_t': march_t,
                    'months': len(in_period),
                }
            )
        table = pd.DataFrame(rows).set_index('years')
        table.to_csv(self.output_directory / 'table_6_subperiods.csv')
        return f'### 6/6 winners minus losers by five-year subperiod (Table VI)\n\n{markdown_table.MarkdownTable(table).render()}'
