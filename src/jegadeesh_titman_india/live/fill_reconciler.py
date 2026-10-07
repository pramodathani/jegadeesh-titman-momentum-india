"""Finds out how much of each placed order actually filled, by reading the account's order book.

UBI's order engine sends market orders as marketable limits that follow the book for 30 seconds and are then cancelled, so an order can be accepted and still fill only partly, or not at all. A strategy's book must be updated with the filled quantities, not the ordered ones.

Typical usage example:

  reconciler = FillReconciler()
  fills = reconciler.fills(placement_results)
"""

import pandas as pd

from tradingmachine.assets import instruments


ORDER_DETAILS_PATH = '/api/orders/details'


class FillReconciler:
    """The reader of filled quantities and prices for a set of placed orders."""

    def __init__(self, unified_broker_interface=None):
        """Initialises the reconciler.

        Args:
            unified_broker_interface: The tradingmachine UnifiedBrokerInterface to read the order book through, or None to share the one every instrument uses.

        Raises:
            ValueError: No client was given and the shared client is not configured.
        """
        if unified_broker_interface is None:
            unified_broker_interface = instruments.Instrument.shared_unified_broker_interface()
        self._unified_broker_interface = unified_broker_interface

    def fills(self, placement_results: pd.DataFrame) -> pd.DataFrame:
        """Matches each placed order to the account's order book and adds up what filled.

        An order is matched on the engine's `intent_id` when the placement gave one, and otherwise on its `order_id`.

        Args:
            placement_results: A pandas.DataFrame as Portfolio.place_orders returns it, with `instrument_id`, `transaction_type`, `quantity`, `intent_id` and `order_id` columns.

        Returns:
            A pandas.DataFrame with one row per placed order: `instrument_id`, `label`, `transaction_type`, `ordered_quantity`, `filled_quantity` and `average_price`, the price None when nothing filled.

        Raises:
            ServiceUnavailableError: UBI's order book is missing or too old to serve.
            UnifiedBrokerInterfaceError: Any other failure reported by, or on the way to, UBI.
        """
        book_rows = self._unified_broker_interface.get(ORDER_DETAILS_PATH)['orders']
        rows = []
        for placed in placement_results.to_dict('records'):
            matching = []
            for book_row in book_rows:
                same_intent = placed.get('intent_id') and book_row.get('intent_id') == placed.get('intent_id')
                same_order = placed.get('order_id') and str(book_row.get('order_id')) == str(placed.get('order_id'))
                if same_intent or same_order:
                    matching.append(book_row)
            filled_quantity = 0.0
            filled_value = 0.0
            for book_row in matching:
                quantity = float(book_row.get('filled_quantity') or 0)
                price = float(book_row.get('average_price') or 0)
                filled_quantity += quantity
                filled_value += quantity * price
            average_price = None
            if filled_quantity > 0:
                average_price = filled_value / filled_quantity
            rows.append(
                {
                    'instrument_id': placed['instrument_id'],
                    'label': placed.get('label'),
                    'transaction_type': placed['transaction_type'],
                    'ordered_quantity': float(placed['quantity']),
                    'filled_quantity': filled_quantity,
                    'average_price': average_price,
                }
            )
        return pd.DataFrame(rows)
