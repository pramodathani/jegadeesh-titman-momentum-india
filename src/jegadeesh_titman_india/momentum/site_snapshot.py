"""Writes the small data files the web app reads, from the study's results.

Every one of the 64 portfolios is built from the same blocks: its holdings in a month are the winners decile of its last K monthly cohorts. So the app needs only the winners decile at every month-end for each ranking period, gap and universe (16 combinations), and works out holdings, joiners and leavers itself. Raw NSE prices are not written, only the study's derived results.

Files written under the output directory:

- `meta.json`: share symbols, the 64 strategies, months covered, and the paper's and India's Table I spreads; the paper's numbers are read from `paper_table_one.csv`, typed in from the paper.
- `cohorts/<universe>_j<J>_skip<days>.json`: for each month-end, the winners decile as rows of symbol number, ranking return, traded value in rupees crore and liquidity tercile.
- `returns.json`: monthly returns of the 64 portfolios before and after costs, their turnover, the NIFTY 500 total return and the equal-weighted market.
- `stats.json`: the 64-row comparison table.

Typical usage example:

  snapshot = SiteSnapshot(panel, comparison_frame, comparison_table, benchmark_returns, table_one_by_universe)
  snapshot.write(output_directory)
"""

import json
import math
import pathlib

import numpy as np
import pandas as pd

from jegadeesh_titman_india.live import strategy_specification
from jegadeesh_titman_india.momentum import decile_ranker
from jegadeesh_titman_india.momentum import monthly_return_panel
from jegadeesh_titman_india.momentum import universe_filter


WINNERS = 10

MOST_TRADED_COUNT = 500

CRORE = 1e7

PAPER_TABLE_ONE_FILE = pathlib.Path(__file__).resolve().parent / 'paper_table_one.csv'

PAPER_TABLE_ONE_SOURCE = 'Jegadeesh and Titman (1993), Table I, buy minus sell, NYSE and AMEX, 1965-1989'


class SiteSnapshot:
    """The web app's data, built from one run of the study.

    Attributes:
        panel: The monthly_return_panel.MonthlyReturnPanel of share returns.
        comparison_frame: A pandas.DataFrame as PortfolioComparison.net_returns returns it.
        comparison_table: A pandas.DataFrame as PortfolioComparison.table returns it.
        benchmark_returns: A pandas.Series of NIFTY 500 total returns indexed by month.
        table_one_by_universe: A dict mapping each str universe name to a pandas.DataFrame as StrategyGrid.table_one returns it.
    """

    def __init__(
        self,
        panel: monthly_return_panel.MonthlyReturnPanel,
        comparison_frame: pd.DataFrame,
        comparison_table: pd.DataFrame,
        benchmark_returns: pd.Series,
        table_one_by_universe: dict,
    ):
        """Initialises the snapshot.

        Args:
            panel: The monthly_return_panel.MonthlyReturnPanel of share returns.
            comparison_frame: A pandas.DataFrame of net, gross and turnover columns per strategy.
            comparison_table: A pandas.DataFrame of the 64-row comparison.
            benchmark_returns: A pandas.Series of NIFTY 500 total returns indexed by month.
            table_one_by_universe: A dict mapping each str universe name to its Table I frame.

        Raises:
            Nothing.
        """
        self.panel = panel
        self.comparison_frame = comparison_frame
        self.comparison_table = comparison_table
        self.benchmark_returns = benchmark_returns
        self.table_one_by_universe = table_one_by_universe
        self._symbol_numbers = {}
        for number, symbol in enumerate(panel.symbols):
            self._symbol_numbers[symbol] = number

    def write(self, output_directory: pathlib.Path) -> dict:
        """Writes every data file.

        Args:
            output_directory: The pathlib.Path of the app's data folder.

        Returns:
            A dict mapping each written file's str name to its size in bytes.

        Raises:
            OSError: A file cannot be written.
        """
        cohort_directory = output_directory / 'cohorts'
        cohort_directory.mkdir(parents=True, exist_ok=True)
        sizes = {}
        ranker = decile_ranker.DecileRanker()
        for universe_name in strategy_specification.UNIVERSE_SHORT_NAMES:
            most_traded_count = MOST_TRADED_COUNT if universe_name == 'most_traded_500' else None
            universe = universe_filter.UniverseFilter(self.panel, most_traded_count=most_traded_count)
            for ranking_months in strategy_specification.RANKING_MONTHS:
                eligible = universe.eligible(ranking_months)
                terciles = universe.liquidity_terciles(ranking_months).to_numpy()
                traded_value = universe.panel.trailing_traded_value(universe.liquidity_months).to_numpy()
                for skipped_days in strategy_specification.SKIPPED_DAYS:
                    ranking_returns = self.panel.ranking_returns(ranking_months, skipped_days)
                    deciles = ranker.assign(ranking_returns, eligible)
                    document = self._cohort_document(deciles, ranking_returns.to_numpy(), traded_value, terciles)
                    universe_short = strategy_specification.UNIVERSE_SHORT_NAMES[universe_name]
                    file_name = f'{universe_short}_j{ranking_months}_skip{skipped_days}.json'
                    sizes['cohorts/' + file_name] = self._write_json(cohort_directory / file_name, document)
        sizes['returns.json'] = self._write_json(output_directory / 'returns.json', self._returns_document())
        sizes['stats.json'] = self._write_json(output_directory / 'stats.json', self._stats_document())
        sizes['meta.json'] = self._write_json(output_directory / 'meta.json', self._meta_document())
        return sizes

    def _cohort_document(
        self,
        deciles: np.ndarray,
        ranking_returns: np.ndarray,
        traded_value: np.ndarray,
        terciles: np.ndarray,
    ) -> dict:
        """Lists the winners decile at every month-end that formed one.

        Args:
            deciles: A numpy.ndarray of ints, months by symbols, from DecileRanker.assign.
            ranking_returns: A numpy.ndarray of floats with the same shape.
            traded_value: A numpy.ndarray of trailing traded values in rupees with the same shape.
            terciles: A numpy.ndarray of liquidity terciles, 1 to 3 or NaN, with the same shape.

        Returns:
            A dict with `months`, a list of str `YYYY-MM` formation months, and `members`, a list holding for each month a list of [symbol number, ranking return, traded value in crore, tercile] rows, largest ranking return first.

        Raises:
            Nothing.
        """
        months = []
        members = []
        for month_position, month in enumerate(self.panel.months):
            winners = np.nonzero(deciles[month_position] == WINNERS)[0]
            if len(winners) == 0:
                continue
            rows = []
            for column in winners:
                tercile = terciles[month_position, column]
                rows.append(
                    [
                        int(column),
                        round(float(ranking_returns[month_position, column]), 4),
                        self._rounded(traded_value[month_position, column] / CRORE, 2),
                        None if math.isnan(tercile) else int(tercile),
                    ]
                )
            rows.sort(key=lambda row: row[1], reverse=True)
            months.append(str(month))
            members.append(rows)
        return {
            'months': months,
            'members': members,
        }

    def _returns_document(self) -> dict:
        """Collects the monthly return series the app charts.

        Returns:
            A dict with `months`, `benchmark`, `equal_weighted` and `strategies`, where each strategy maps to `net`, `gross` and `turnover` lists aligned with `months`, null where there is no value.

        Raises:
            Nothing.
        """
        months = self.comparison_frame.index
        strategies = {}
        for specification in strategy_specification.StrategySpecification.all_specifications():
            name = specification.name
            strategies[name] = {
                'net': self._series_list(self.comparison_frame[name], 5),
                'gross': self._series_list(self.comparison_frame[name + '__gross'], 5),
                'turnover': self._series_list(self.comparison_frame[name + '__turnover'], 4),
            }
        return {
            'months': [str(month) for month in months],
            'benchmark': self._series_list(self.benchmark_returns.reindex(months), 5),
            'equal_weighted': self._series_list(self.panel.equal_weighted_market_returns().reindex(months), 5),
            'strategies': strategies,
        }

    def _stats_document(self) -> list[dict]:
        """Turns the comparison table into a list of records.

        Returns:
            A list of dicts, one per strategy, with the comparison table's columns and a `strategy` name.

        Raises:
            Nothing.
        """
        records = []
        for name, row in self.comparison_table.iterrows():
            record = {
                'strategy': name,
            }
            for column, value in row.items():
                if isinstance(value, float):
                    record[column] = self._rounded(value, 5)
                elif isinstance(value, (np.integer, int)):
                    record[column] = int(value)
                else:
                    record[column] = value
            records.append(record)
        return records

    def _meta_document(self) -> dict:
        """Describes the data: symbols, strategies, dates and both Table I grids.

        Returns:
            A dict of the app's reference data.

        Raises:
            Nothing.
        """
        strategies = []
        for specification in strategy_specification.StrategySpecification.all_specifications():
            strategies.append(
                {
                    'name': specification.name,
                    'ranking_months': specification.ranking_months,
                    'holding_months': specification.holding_months,
                    'skipped_days': specification.skipped_days,
                    'universe': strategy_specification.UNIVERSE_SHORT_NAMES[specification.universe_name],
                }
            )
        india_table_one = {}
        for universe_name, table in self.table_one_by_universe.items():
            spreads = table[table['portfolio'] == 'buy_minus_sell']
            universe_short = strategy_specification.UNIVERSE_SHORT_NAMES[universe_name]
            india_table_one[universe_short] = self._table_one_grid(spreads)
        paper_table_one = self._table_one_grid(pd.read_csv(PAPER_TABLE_ONE_FILE))
        return {
            'generated': pd.Timestamp.now().strftime('%Y-%m-%d'),
            'first_month': str(self.panel.months[0]),
            'latest_formation_month': str(self.panel.months[-1]),
            'symbols': [str(symbol) for symbol in self.panel.symbols],
            'strategies': strategies,
            'holding_months': strategy_specification.HOLDING_MONTHS,
            'ranking_months': strategy_specification.RANKING_MONTHS,
            'skipped_days': strategy_specification.SKIPPED_DAYS,
            'paper_table_one_source': PAPER_TABLE_ONE_SOURCE,
            'paper_table_one': paper_table_one,
            'india_table_one': india_table_one,
            'india_table_one_months': f'{self.table_one_by_universe["most_traded_500"]["first_month"].iloc[0]} to {self.table_one_by_universe["most_traded_500"]["last_month"].iloc[0]}',
        }

    def _table_one_grid(self, spreads: pd.DataFrame) -> dict:
        """Arranges Table I spreads as the app reads them.

        Args:
            spreads: A pandas.DataFrame with `skipped_days`, `ranking_months`, `holding_months`, `mean` and `t_statistic` columns, one row per strategy.

        Returns:
            A dict keyed `skip0` and `skip5`, each mapping a str ranking period to a list of [mean, t-statistic] pairs for holding periods 3, 6, 9 and 12.

        Raises:
            IndexError: A strategy is missing from spreads.
        """
        grid = {}
        for skipped_days in strategy_specification.SKIPPED_DAYS:
            panel_grid = {}
            for ranking_months in strategy_specification.RANKING_MONTHS:
                cells = []
                for holding_months in strategy_specification.HOLDING_MONTHS:
                    match = spreads[
                        (spreads['skipped_days'] == skipped_days)
                        & (spreads['ranking_months'] == ranking_months)
                        & (spreads['holding_months'] == holding_months)
                    ].iloc[0]
                    cells.append(
                        [
                            self._rounded(match['mean'], 5),
                            self._rounded(match['t_statistic'], 2),
                        ]
                    )
                panel_grid[str(ranking_months)] = cells
            grid[f'skip{skipped_days}'] = panel_grid
        return grid

    def _series_list(self, series: pd.Series, decimals: int) -> list:
        """Turns a series into a JSON-ready list with nulls for missing values.

        Args:
            series: A pandas.Series of floats.
            decimals: The int number of decimal places to keep.

        Returns:
            A list of floats and None values.

        Raises:
            Nothing.
        """
        values = []
        for value in series.to_numpy():
            values.append(self._rounded(value, decimals))
        return values

    def _rounded(self, value: float, decimals: int) -> float | None:
        """Rounds a value, giving None for NaN or infinity.

        Args:
            value: The float to round.
            decimals: The int number of decimal places.

        Returns:
            The rounded float, or None.

        Raises:
            Nothing.
        """
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, decimals)

    def _write_json(self, file_path: pathlib.Path, document) -> int:
        """Writes a document as compact JSON.

        Args:
            file_path: The pathlib.Path to write.
            document: The dict or list to write.

        Returns:
            The int size of the file in bytes.

        Raises:
            OSError: The file cannot be written.
        """
        file_path.write_text(json.dumps(document, separators=(',', ':')))
        return file_path.stat().st_size
