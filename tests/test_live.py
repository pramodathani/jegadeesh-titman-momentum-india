"""Tests of the live portfolio code that need no connection to UBI or MongoDB, skipped when the optional tradingmachine library is not installed.

Run from the repository root:

  python -m pytest
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip('tradingmachine')

from jegadeesh_titman_india.live import live_rebalancer
from jegadeesh_titman_india.live import strategy_specification
from jegadeesh_titman_india.momentum import overlapping_strategy


class FakeBook:
    """A stand-in for StrategyBook that keeps holdings in memory."""

    def __init__(self, holdings: dict):
        """Initialises the fake book.

        Args:
            holdings: A dict in the form StrategyBook.load returns.

        Raises:
            Nothing.
        """
        self.holdings = holdings

    def load(self) -> dict:
        """Gives the holdings.

        Returns:
            The dict of holdings.

        Raises:
            Nothing.
        """
        return self.holdings


class TestStrategySpecification:
    """Tests of StrategySpecification."""

    def test_there_are_64_uniquely_named_specifications_with_short_tags(self):
        """Checks the count, that names are unique, that names round-trip and that tags fit brokers' limits.

        Returns:
            None.

        Raises:
            AssertionError: A check fails.
        """
        specifications = strategy_specification.StrategySpecification.all_specifications()
        names = set()
        for specification in specifications:
            names.add(specification.name)
            assert len(specification.tag) <= 10
            assert strategy_specification.StrategySpecification.from_name(specification.name).name == specification.name
        assert len(specifications) == 64
        assert len(names) == 64

    def test_unknown_values_are_refused(self):
        """Checks that a holding period the paper does not use is refused.

        Returns:
            None.

        Raises:
            AssertionError: No error was raised.
        """
        with pytest.raises(ValueError):
            strategy_specification.StrategySpecification(6, 5, 0, 'most_traded_500')


class TestNextMonthWeights:
    """Tests of OverlappingStrategy.next_month_weights."""

    def test_weights_come_from_the_last_k_cohorts(self):
        """Checks that with K of 2 only the last two cohorts count, each with half the weight.

        Returns:
            None.

        Raises:
            AssertionError: The weights are wrong.
        """
        monthly_returns = pd.DataFrame(np.zeros((3, 20)), columns=[f'S{number}' for number in range(20)])
        deciles = np.tile(np.repeat(np.arange(1, 11), 2), (3, 1))
        deciles[0] = np.repeat(np.arange(10, 0, -1), 2)
        deciles[2, 18] = 9
        deciles[2, 17] = 10
        strategy = overlapping_strategy.OverlappingStrategy(monthly_returns, deciles, holding_months=2)
        weights = strategy.next_month_weights(10)
        assert weights.sum() == pytest.approx(1.0)
        assert set(weights.index) == {'S17', 'S18', 'S19'}
        assert weights['S19'] == pytest.approx(0.5)
        assert weights['S18'] == pytest.approx(0.25)
        assert weights['S17'] == pytest.approx(0.25)


class TestApplyFills:
    """Tests of LiveRebalancer._apply_fills."""

    def test_buys_average_in_and_sells_reduce_or_remove(self):
        """Checks a partial buy, a full sale and a new purchase against a book.

        Returns:
            None.

        Raises:
            AssertionError: The updated book is wrong.
        """
        specification = strategy_specification.StrategySpecification(6, 6, 0, 'most_traded_500')
        book = FakeBook(
            {
                'id-a': {
                    'label': 'nse:A',
                    'quantity': 10.0,
                    'average_price': 100.0,
                },
                'id-b': {
                    'label': 'nse:B',
                    'quantity': 5.0,
                    'average_price': 50.0,
                },
            }
        )
        rebalancer = live_rebalancer.LiveRebalancer(specification, target_index=None, capital=1000.0, book=book)
        rebalancer._holdings = book.load()
        fills = pd.DataFrame(
            [
                {
                    'instrument_id': 'id-a',
                    'label': 'nse:A',
                    'transaction_type': 'buy',
                    'ordered_quantity': 20.0,
                    'filled_quantity': 10.0,
                    'average_price': 120.0,
                },
                {
                    'instrument_id': 'id-b',
                    'label': 'nse:B',
                    'transaction_type': 'sell',
                    'ordered_quantity': 5.0,
                    'filled_quantity': 5.0,
                    'average_price': 55.0,
                },
                {
                    'instrument_id': 'id-c',
                    'label': 'nse:C',
                    'transaction_type': 'buy',
                    'ordered_quantity': 3.0,
                    'filled_quantity': 3.0,
                    'average_price': 10.0,
                },
            ]
        )
        rebalancer._apply_fills(fills)
        assert rebalancer._holdings['id-a']['quantity'] == pytest.approx(20.0)
        assert rebalancer._holdings['id-a']['average_price'] == pytest.approx(110.0)
        assert 'id-b' not in rebalancer._holdings
        assert rebalancer._holdings['id-c']['quantity'] == pytest.approx(3.0)
