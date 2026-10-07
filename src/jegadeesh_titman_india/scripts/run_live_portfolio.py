"""Rebalances one momentum strategy in the live account at the start of a month.

A strategy is rebalanced at most once a calendar month: a real run refuses to start when the strategy's book was already saved this month, unless `--force` is given, so the command can safely be scheduled on several mornings in a row.

Without `--execute`, nothing is sent: the trades are worked out against the strategy's own book and UBI builds each order as a dry run, so the plan can be checked. With `--execute`, real delivery orders are placed, sells first and buys after, and the strategy's book is updated with what filled. `--confirm` must repeat the strategy name, so a real run cannot start by accident.

Run from the repository root on the first trading day of the month, during market hours, after fetching last month's prices:

  python -m jegadeesh_titman_india.scripts.fetch_tradingmachine_prices
  python -m jegadeesh_titman_india.scripts.run_live_portfolio --strategy jt-momentum-j6-k6-skip0-top500 --capital 500000
  python -m jegadeesh_titman_india.scripts.run_live_portfolio --strategy jt-momentum-j6-k6-skip0-top500 --capital 500000 --execute --confirm jt-momentum-j6-k6-skip0-top500
"""

import argparse
import logging
import pathlib

import pandas as pd

from jegadeesh_titman_india.live import live_panel
from jegadeesh_titman_india.live import live_rebalancer
from jegadeesh_titman_india.live import momentum_target
from jegadeesh_titman_india.live import strategy_book
from jegadeesh_titman_india.live import strategy_specification


STUDY_DIRECTORY = pathlib.Path(__file__).resolve().parents[3]

CACHE_DIRECTORY = STUDY_DIRECTORY / 'data' / 'tradingmachine'

LOG_DIRECTORY = STUDY_DIRECTORY / 'results' / 'live_runs'


class RunLivePortfolioApplication:
    """The command-line program that rebalances one strategy, as a dry run unless confirmed."""

    def run(self) -> None:
        """Reads the command line, plans the rebalance and sends it as a dry run or for real.

        Returns:
            None.

        Raises:
            SystemExit: `--execute` was given without a matching `--confirm`.
            StalePricesError: The price cache does not reach the end of last month.
            HoldingsShortfallError: The account holds less than the strategy would sell.
        """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        parser = argparse.ArgumentParser(description='Rebalance one momentum strategy.')
        parser.add_argument('--strategy', required=True)
        parser.add_argument('--capital', type=float, required=True)
        parser.add_argument('--execute', action='store_true')
        parser.add_argument('--confirm', default=None)
        parser.add_argument('--force', action='store_true')
        arguments = parser.parse_args()
        if arguments.execute and arguments.confirm != arguments.strategy:
            parser.error('--execute places real orders; repeat the strategy name with --confirm to go ahead')
        specification = strategy_specification.StrategySpecification.from_name(arguments.strategy)
        book = strategy_book.StrategyBook(specification)
        last_saved = book.last_saved_date()
        this_month = pd.Timestamp.now().to_period('M')
        if arguments.execute and not arguments.force and last_saved is not None and pd.Timestamp(last_saved).to_period('M') == this_month:
            logging.info('%s was already rebalanced on %s; nothing to do this month', specification.name, last_saved)
            return
        panel = live_panel.LivePanel(CACHE_DIRECTORY).build()
        target = momentum_target.MomentumTarget(panel, specification)
        logging.info('Target for %s formed at the end of %s: %s shares', specification.name, target.formation_month, len(target.weights()))
        rebalancer = live_rebalancer.LiveRebalancer(specification, target.to_index(), arguments.capital, book=book)
        trades = rebalancer.plan()
        dry_run = not arguments.execute
        report = rebalancer.execute(trades, dry_run=dry_run)
        self._write_log(specification, target, trades, report, dry_run)
        self._print_summary(trades, report, dry_run, arguments.capital)

    def _write_log(self, specification, target, trades: pd.DataFrame, report: dict, dry_run: bool) -> None:
        """Saves the plan, the orders and the fills of this run as CSV files.

        Args:
            specification: The strategy_specification.StrategySpecification traded.
            target: The momentum_target.MomentumTarget used.
            trades: The pandas.DataFrame of planned trades.
            report: The dict LiveRebalancer.execute returned.
            dry_run: A bool that is True when nothing was sent.

        Returns:
            None.

        Raises:
            OSError: A file cannot be written.
        """
        mode = 'dry_run' if dry_run else 'executed'
        stamp = pd.Timestamp.now().strftime('%Y-%m-%dT%H%M%S')
        directory = LOG_DIRECTORY / specification.name / f'{stamp}_{mode}'
        directory.mkdir(parents=True, exist_ok=True)
        target.weights().rename('weight').rename_axis('symbol').to_csv(directory / 'target_weights.csv')
        trades.to_csv(directory / 'planned_trades.csv', index=False)
        for key, frame in report.items():
            if frame is not None:
                frame.to_csv(directory / f'{key}.csv', index=False)
        logging.info('Wrote this run to %s', directory)

    def _print_summary(self, trades: pd.DataFrame, report: dict, dry_run: bool, capital: float) -> None:
        """Prints what was planned and what happened.

        Args:
            trades: The pandas.DataFrame of planned trades.
            report: The dict LiveRebalancer.execute returned.
            dry_run: A bool that is True when nothing was sent.
            capital: The float rupees the strategy is sized to.

        Returns:
            None.

        Raises:
            Nothing.
        """
        trade_value = (trades['trade_quantity'].abs() * trades['last_price']).sum()
        target_value = (trades['target_quantity'] * trades['last_price']).sum()
        print(f'Mode: {"DRY RUN, nothing sent" if dry_run else "EXECUTED"}')
        print(f'Capital {capital:,.0f}; invested after rebalance {target_value:,.0f}; traded {trade_value:,.0f}')
        print(f'Sells: {int((trades["trade_quantity"] < 0).sum())}; buys: {int((trades["trade_quantity"] > 0).sum())}')
        print(trades.drop(columns=['instrument_id']).to_string(index=False))
        for key, frame in report.items():
            if frame is not None and 'status' in frame.columns:
                print(f'{key}: HTTP status counts {frame["status"].value_counts().to_dict()}')
            elif frame is not None:
                print(f'{key}: filled {frame["filled_quantity"].sum():.0f} of {frame["ordered_quantity"].sum():.0f} units')


if __name__ == '__main__':
    RunLivePortfolioApplication().run()
