"""Moves one live strategy from what its book holds to this month's momentum target.

The steps are: work out the trades against the strategy's own book, check the demat account really holds what is to be sold, send the sells, wait for UBI's 30-second marketable limits to finish and read what filled, then do the same for the buys, and finally store the new book. Sells go first so their proceeds can pay for the buys.

With dry_run, UBI builds every order without sending it and the book is not changed.

Typical usage example:

  rebalancer = LiveRebalancer(specification, target_index, capital=500000)
  trades = rebalancer.plan()
  report = rebalancer.execute(trades, dry_run=True)
"""

import logging
import math
import time

import pandas as pd

from tradingmachine.asset_baskets import index
from tradingmachine.asset_baskets import member_resolver
from tradingmachine.asset_baskets import portfolio
from tradingmachine.assets import instruments

from jegadeesh_titman_india.live import fill_reconciler
from jegadeesh_titman_india.live import strategy_book
from jegadeesh_titman_india.live import strategy_specification


HOLDINGS_PATH = '/api/portfolio/holdings'

DELIVERY_PRODUCT = 'cnc'

SECONDS_TO_WAIT_FOR_FILLS = 45

TRADE_COLUMNS = [
    'label',
    'instrument_id',
    'last_price',
    'current_quantity',
    'target_quantity',
    'trade_quantity',
    'transaction_type',
]


class HoldingsShortfallError(RuntimeError):
    """The demat account holds less of a share than the strategy's book says it should sell."""


class LiveRebalancer:
    """One rebalance of one live strategy.

    Attributes:
        specification: The strategy_specification.StrategySpecification being traded.
        target_index: The tradingmachine Index holding this month's target weights.
        capital: The float rupees the strategy should be worth after the rebalance.
        book: The strategy_book.StrategyBook holding what the strategy owns.
    """

    def __init__(
        self,
        specification: strategy_specification.StrategySpecification,
        target_index: index.Index,
        capital: float,
        book: strategy_book.StrategyBook | None = None,
    ):
        """Initialises the rebalance.

        Args:
            specification: The strategy_specification.StrategySpecification being traded.
            target_index: The tradingmachine Index holding this month's target weights.
            capital: The float rupees the strategy should be worth after the rebalance.
            book: The strategy_book.StrategyBook to read and write, or None to use the strategy's default book.

        Raises:
            ValueError: capital is not positive.
        """
        if capital <= 0:
            raise ValueError(f'capital must be positive: {capital=}')
        self.specification = specification
        self.target_index = target_index
        self.capital = capital
        self.book = book if book is not None else strategy_book.StrategyBook(specification)
        self._holdings = None

    def plan(self) -> pd.DataFrame:
        """Works out the trades that move the strategy's book to the target, without sending anything.

        Returns:
            A pandas.DataFrame with `label`, `instrument_id`, `last_price`, `current_quantity`, `target_quantity`, `trade_quantity`, negative for a sale, and `transaction_type`, sells first.

        Raises:
            BasketMemberError: A share has no last price.
            UnifiedBrokerInterfaceError: UBI refused a request or could not be reached.
        """
        self._holdings = self.book.load()
        held = self.book.to_portfolio(self._holdings)
        if held is not None:
            return held.rebalance_trades(target=self.target_index, capital=self.capital)
        starting = self.target_index.to_portfolio(capital=self.capital, name=self.specification.name)
        last_prices = starting.last_prices.set_index('instrument_id')['last_price']
        rows = []
        for member in starting.members:
            instrument_id = member.instrument.instrument_id
            rows.append(
                {
                    'label': member.label,
                    'instrument_id': instrument_id,
                    'last_price': float(last_prices.get(instrument_id, math.nan)),
                    'current_quantity': 0.0,
                    'target_quantity': float(member.quantity),
                    'trade_quantity': float(member.quantity),
                    'transaction_type': portfolio.BUY,
                }
            )
        return pd.DataFrame(rows, columns=TRADE_COLUMNS)

    def execute(self, trades: pd.DataFrame, dry_run: bool = True) -> dict:
        """Sends the sells, then the buys, and stores the new book unless this is a dry run.

        Args:
            trades: A pandas.DataFrame as plan returns it.
            dry_run: A bool that is True to have UBI build the orders without sending them, leaving the book unchanged.

        Returns:
            A dict with pandas.DataFrame values `sell_orders` and `buy_orders` as Portfolio.place_orders returns them, and, unless dry_run, `sell_fills` and `buy_fills` as FillReconciler.fills returns them; a side with no trades has None.

        Raises:
            HoldingsShortfallError: The demat account holds less of a share than is to be sold.
            ServiceUnavailableError: UBI's order engine is not running.
            UnifiedBrokerInterfaceError: Any other failure of a whole request.
        """
        if self._holdings is None:
            self._holdings = self.book.load()
        sells = trades[trades['trade_quantity'] < 0]
        buys = trades[trades['trade_quantity'] > 0]
        report = {
            'sell_orders': None,
            'buy_orders': None,
            'sell_fills': None,
            'buy_fills': None,
        }
        if not dry_run and len(sells) > 0:
            self._check_demat_holdings(sells)
        reconciler = fill_reconciler.FillReconciler()
        sides = [
            ('sell', sells, portfolio.SELL),
            ('buy', buys, portfolio.BUY),
        ]
        for side_name, side_trades, transaction_type in sides:
            if len(side_trades) == 0:
                continue
            orders = self._place(side_trades, transaction_type, dry_run)
            report[f'{side_name}_orders'] = orders
            if dry_run:
                continue
            logging.info('Waiting %s seconds for %s orders to finish', SECONDS_TO_WAIT_FOR_FILLS, side_name)
            time.sleep(SECONDS_TO_WAIT_FOR_FILLS)
            fills = reconciler.fills(orders)
            report[f'{side_name}_fills'] = fills
            self._apply_fills(fills)
        if not dry_run:
            self.book.save(self._holdings)
        return report

    def _place(self, side_trades: pd.DataFrame, transaction_type: str, dry_run: bool) -> pd.DataFrame:
        """Sends one side's orders in a single list request.

        Args:
            side_trades: The pandas.DataFrame rows of plan for one side.
            transaction_type: The str side, `buy` or `sell`.
            dry_run: A bool that is True to have UBI build the orders without sending them.

        Returns:
            A pandas.DataFrame as Portfolio.place_orders returns it.

        Raises:
            ServiceUnavailableError: UBI's order engine is not running.
            UnifiedBrokerInterfaceError: Any other failure of the whole request.
        """
        rows = []
        for trade in side_trades.to_dict('records'):
            rows.append(
                {
                    'instrument_id': trade['instrument_id'],
                    'quantity': abs(trade['trade_quantity']),
                }
            )
        resolver = member_resolver.MemberResolver()
        members = resolver.resolve(rows)
        orders = portfolio.Portfolio(
            name=f'{self.specification.name}-{transaction_type}s',
            members=members,
            unified_broker_interface=resolver.unified_broker_interface,
        )
        return orders.place_orders(
            product=DELIVERY_PRODUCT,
            transaction_type=transaction_type,
            tag=self.specification.tag,
            dry_run=dry_run,
        )

    def _check_demat_holdings(self, sells: pd.DataFrame) -> None:
        """Makes sure the demat account holds enough of every share the strategy is about to sell.

        Args:
            sells: The pandas.DataFrame rows of plan with negative trade quantities.

        Returns:
            None.

        Raises:
            HoldingsShortfallError: A share is held in a smaller quantity than is to be sold.
            UnifiedBrokerInterfaceError: UBI refused the request or could not be reached.
        """
        client = instruments.Instrument.shared_unified_broker_interface()
        answer = client.get(HOLDINGS_PATH)
        held_quantity = {}
        for holding in answer['holdings']:
            instrument_id = holding.get('instrument_id')
            held_quantity[instrument_id] = held_quantity.get(instrument_id, 0.0) + float(holding.get('quantity') or 0)
        shortfalls = []
        for sell in sells.to_dict('records'):
            needed = abs(sell['trade_quantity'])
            if held_quantity.get(sell['instrument_id'], 0.0) < needed:
                shortfalls.append(f"{sell['label']}: need {needed:.0f}, hold {held_quantity.get(sell['instrument_id'], 0.0):.0f}")
        if shortfalls:
            raise HoldingsShortfallError('The account holds less than the strategy would sell: ' + '; '.join(shortfalls))

    def _apply_fills(self, fills: pd.DataFrame) -> None:
        """Adds filled buys to, and takes filled sells from, the book held in memory.

        Args:
            fills: A pandas.DataFrame as FillReconciler.fills returns it.

        Returns:
            None.

        Raises:
            Nothing.
        """
        for fill in fills.to_dict('records'):
            if fill['filled_quantity'] <= 0:
                continue
            instrument_id = fill['instrument_id']
            holding = self._holdings.get(
                instrument_id,
                {
                    'label': fill['label'],
                    'quantity': 0.0,
                    'average_price': None,
                },
            )
            if fill['transaction_type'] == portfolio.BUY:
                old_cost = holding['quantity'] * (holding['average_price'] or 0.0)
                new_quantity = holding['quantity'] + fill['filled_quantity']
                holding['average_price'] = (old_cost + fill['filled_quantity'] * fill['average_price']) / new_quantity
                holding['quantity'] = new_quantity
            else:
                holding['quantity'] = holding['quantity'] - fill['filled_quantity']
            if holding['quantity'] > 0:
                self._holdings[instrument_id] = holding
            else:
                self._holdings.pop(instrument_id, None)
