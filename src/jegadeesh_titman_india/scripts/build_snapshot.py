"""Builds the web app's data files from the bhavcopy study, ready to publish.

Run from the repository root after run_study, which writes the Table I files this reads:

  python -m jegadeesh_titman_india.scripts.build_snapshot

The files are written to `src/jegadeesh_titman_india/site/data/`, inside the package, so that they ship with it and GitHub Pages can serve them.
"""

import logging
import pathlib

import pandas as pd

from jegadeesh_titman_india.momentum import benchmark_history
from jegadeesh_titman_india.momentum import implausible_move_filter
from jegadeesh_titman_india.momentum import monthly_return_panel
from jegadeesh_titman_india.momentum import portfolio_comparison
from jegadeesh_titman_india.momentum import site_snapshot
from jegadeesh_titman_india.momentum.price_sources import bhavcopy_price_source


STUDY_DIRECTORY = pathlib.Path(__file__).resolve().parents[3]

DATA_DIRECTORY = STUDY_DIRECTORY / 'data'

RESULTS_DIRECTORY = STUDY_DIRECTORY / 'results' / 'bhavcopy_from_2005'

SITE_DATA_DIRECTORY = pathlib.Path(__file__).resolve().parents[1] / 'site' / 'data'

FIRST_DAY = pd.Timestamp('2005-01-01')

LAST_COMPLETE_DAY = pd.Timestamp('2026-09-30')

UNIVERSE_NAMES = [
    'most_traded_500',
    'all_shares',
]


class BuildSnapshotApplication:
    """The command-line program that writes the web app's data."""

    def run(self) -> None:
        """Builds the panel and comparison, and writes the snapshot files.

        Returns:
            None.

        Raises:
            FileNotFoundError: The bhavcopy store, index history or run_study results are missing.
        """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        source = bhavcopy_price_source.BhavcopyPriceSource(
            DATA_DIRECTORY / 'bhavcopy' / 'store',
            DATA_DIRECTORY / 'bhavcopy' / 'corporate_actions',
        )
        daily_panel = source.daily_panel()
        in_sample = (daily_panel['date'] >= FIRST_DAY) & (daily_panel['date'] <= LAST_COMPLETE_DAY)
        daily_panel = implausible_move_filter.ImplausibleMoveFilter().clean(daily_panel[in_sample])
        panel = monthly_return_panel.MonthlyReturnPanel(daily_panel)
        benchmark = benchmark_history.BenchmarkHistory(DATA_DIRECTORY).monthly_returns(total_return=True)
        comparison = portfolio_comparison.PortfolioComparison(panel, benchmark, 'NIFTY 500 total return')
        table_one_by_universe = {}
        for universe_name in UNIVERSE_NAMES:
            table_one_by_universe[universe_name] = pd.read_csv(RESULTS_DIRECTORY / f'{universe_name}_table_1_all_strategies.csv')
        snapshot = site_snapshot.SiteSnapshot(
            panel=panel,
            comparison_frame=comparison.net_returns(),
            comparison_table=comparison.table(),
            benchmark_returns=benchmark,
            table_one_by_universe=table_one_by_universe,
        )
        sizes = snapshot.write(SITE_DATA_DIRECTORY)
        total = 0
        for file_name, size in sorted(sizes.items()):
            logging.info('%s: %.0f KB', file_name, size / 1024)
            total += size
        logging.info('Wrote %s files, %.1f MB in all, to %s', len(sizes), total / 1024 / 1024, SITE_DATA_DIRECTORY)


if __name__ == '__main__':
    BuildSnapshotApplication().run()
