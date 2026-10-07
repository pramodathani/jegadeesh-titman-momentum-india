"""Creates next month's target portfolio for every strategy combination the paper describes.

For each of the 64 specifications (J of 3, 6, 9 or 12 months, K of 3, 6, 9 or 12 months, with or without a one-week gap, on the 500 most traded NSE shares or on all of them) it writes the target weights to `results/live_targets/<month>/<strategy name>.csv` and a summary to `results/live_targets/<month>/summary.csv`. With `--save-to-store`, each target is also saved as a tradingmachine Index in the BasketStore, in effect from the first day of the coming month.

Run from the repository root, after fetching prices up to the end of last month:

  python -m jegadeesh_titman_india.scripts.fetch_tradingmachine_prices
  python -m jegadeesh_titman_india.scripts.build_live_targets --save-to-store
"""

import argparse
import logging
import pathlib

import pandas as pd

from tradingmachine.asset_baskets import basket_store
from tradingmachine.asset_baskets import member_resolver

from jegadeesh_titman_india.live import live_panel
from jegadeesh_titman_india.live import momentum_target
from jegadeesh_titman_india.live import strategy_specification


STUDY_DIRECTORY = pathlib.Path(__file__).resolve().parents[3]

CACHE_DIRECTORY = STUDY_DIRECTORY / 'data' / 'tradingmachine'

TARGETS_DIRECTORY = STUDY_DIRECTORY / 'results' / 'live_targets'

STORE_SOURCE = 'jegadeesh_titman_target'


class BuildLiveTargetsApplication:
    """The command-line program that forms every strategy's target for the coming month."""

    def run(self) -> None:
        """Builds the panel, forms all 64 targets, writes them and optionally stores them.

        Returns:
            None.

        Raises:
            StalePricesError: The price cache does not reach the end of last month.
            BasketMemberError: UBI could not find a target share while saving to the store.
        """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        parser = argparse.ArgumentParser(description='Form next month\'s momentum targets.')
        parser.add_argument('--save-to-store', action='store_true')
        arguments = parser.parse_args()
        panel = live_panel.LivePanel(CACHE_DIRECTORY).build()
        holding_month = panel.months[-1] + 1
        output_directory = TARGETS_DIRECTORY / str(holding_month)
        output_directory.mkdir(parents=True, exist_ok=True)
        store = None
        resolver = None
        if arguments.save_to_store:
            store = basket_store.BasketStore()
            resolver = member_resolver.MemberResolver()
        summary_rows = []
        for specification in strategy_specification.StrategySpecification.all_specifications():
            target = momentum_target.MomentumTarget(panel, specification)
            weights = target.weights()
            weights.rename('weight').rename_axis('symbol').to_csv(output_directory / f'{specification.name}.csv')
            if store is not None:
                store.save(
                    target.to_index(resolver),
                    effective_date=holding_month.start_time.date(),
                    source=STORE_SOURCE,
                )
            top_symbols = []
            for symbol in weights.index[:5]:
                top_symbols.append(symbol)
            summary_rows.append(
                {
                    'strategy': specification.name,
                    'shares': len(weights),
                    'largest_weight': float(weights.iloc[0]),
                    'smallest_weight': float(weights.iloc[-1]),
                    'largest_holdings': ' '.join(top_symbols),
                }
            )
        summary = pd.DataFrame(summary_rows)
        summary.to_csv(output_directory / 'summary.csv', index=False)
        logging.info('Formed %s targets for %s in %s', len(summary), holding_month, output_directory)
        print(summary.to_string(index=False))


if __name__ == '__main__':
    BuildLiveTargetsApplication().run()
