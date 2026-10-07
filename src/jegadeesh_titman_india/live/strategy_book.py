"""The record of what one live strategy holds, kept apart from the rest of the account.

`Portfolio.from_holdings` reads the whole demat account, so rebalancing it towards a momentum target would also sell every share the strategy never bought. Each strategy therefore keeps its own book: a tradingmachine Portfolio stored in the BasketStore under `<strategy name>-holdings`, saved again after every rebalance with the quantities that actually filled.

Typical usage example:

  book = StrategyBook(specification)
  holdings = book.load()
  book.save(updated_holdings)
"""

import datetime
import logging

import pandas as pd

from tradingmachine.asset_baskets import basket_store
from tradingmachine.asset_baskets import exceptions
from tradingmachine.asset_baskets import member_resolver
from tradingmachine.asset_baskets import portfolio

from jegadeesh_titman_india.live import strategy_specification


BOOK_SUFFIX = '-holdings'

BOOK_SOURCE = 'jegadeesh_titman_live'


class StrategyBook:
    """The stored holdings of one live strategy.

    Attributes:
        specification: The strategy_specification.StrategySpecification whose holdings these are.
        store: The tradingmachine BasketStore the book is kept in.
    """

    def __init__(
        self,
        specification: strategy_specification.StrategySpecification,
        store: basket_store.BasketStore | None = None,
    ):
        """Initialises the book.

        Args:
            specification: The strategy_specification.StrategySpecification whose holdings these are.
            store: The tradingmachine BasketStore to keep the book in, or None to make one from the `.env` settings.

        Raises:
            ValueError: No store was given and the MongoDB settings are not configured.
        """
        self.specification = specification
        self.store = store if store is not None else basket_store.BasketStore()

    @property
    def name(self) -> str:
        """The str name the book is stored under, such as `jt-momentum-j6-k6-skip0-top500-holdings`."""
        return self.specification.name + BOOK_SUFFIX

    def load(self) -> dict:
        """Reads the strategy's latest holdings.

        Returns:
            A dict mapping each str instrument id to a dict with `label`, float `quantity` and float `average_price`, empty when the strategy has never traded.

        Raises:
            BasketMemberError: UBI could not find a stored instrument.
            pymongo.errors.PyMongoError: MongoDB could not be reached.
        """
        try:
            stored = self.store.load(self.name)
        except exceptions.BasketNotFoundError:
            return {}
        holdings = {}
        for member in stored.members:
            if not member.quantity:
                continue
            holdings[member.instrument.instrument_id] = {
                'label': member.label,
                'quantity': float(member.quantity),
                'average_price': member.average_price,
            }
        return holdings

    def last_saved_date(self) -> datetime.date | None:
        """Gives the effective date of the book's latest stored version, which is the day of the last real rebalance.

        Returns:
            The datetime.date of the latest version, or None when the book has never been saved.

        Raises:
            pymongo.errors.PyMongoError: MongoDB could not be reached.
        """
        versions = self.store.history(self.name)
        if versions is None or len(versions) == 0:
            return None
        return pd.Timestamp(versions['effective_date'].max()).date()

    def to_portfolio(self, holdings: dict) -> portfolio.Portfolio | None:
        """Builds a tradingmachine Portfolio from holdings, looking the shares up in one request.

        Args:
            holdings: A dict in the form load returns.

        Returns:
            A tradingmachine Portfolio named after the book, or None when holdings is empty.

        Raises:
            BasketMemberError: UBI could not find one of the shares.
        """
        rows = []
        for instrument_id, holding in holdings.items():
            if holding['quantity'] > 0:
                rows.append(
                    {
                        'instrument_id': instrument_id,
                        'quantity': holding['quantity'],
                        'average_price': holding['average_price'],
                    }
                )
        if not rows:
            return None
        resolver = member_resolver.MemberResolver()
        members = resolver.resolve(rows)
        return portfolio.Portfolio(name=self.name, members=members, unified_broker_interface=resolver.unified_broker_interface)

    def save(self, holdings: dict, effective_date: datetime.date | None = None) -> None:
        """Stores the holdings as the book's version from a date.

        A book whose holdings are all sold cannot be stored as a Portfolio, which needs a member, so that case is logged and the old version is deleted for the date instead.

        Args:
            holdings: A dict in the form load returns.
            effective_date: The datetime.date the holdings are in effect from, or None for today.

        Returns:
            None.

        Raises:
            BasketMemberError: UBI could not find one of the shares.
            pymongo.errors.PyMongoError: MongoDB could not be reached or refused the write.
        """
        if effective_date is None:
            effective_date = datetime.date.today()
        held = self.to_portfolio(holdings)
        if held is None:
            logging.warning('Strategy %s now holds nothing; no book version saved for %s', self.name, effective_date)
            return
        self.store.save(held, effective_date=effective_date, source=BOOK_SOURCE)
