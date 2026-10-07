"""Tests of the momentum study on small synthetic data whose answers are known.

Run from the repository root:

  python -m pytest
"""

import numpy as np
import pandas as pd
import pytest

from jegadeesh_titman_india.momentum import calendar_month_study
from jegadeesh_titman_india.momentum import decile_ranker
from jegadeesh_titman_india.momentum import implausible_move_filter
from jegadeesh_titman_india.momentum import indian_transaction_costs
from jegadeesh_titman_india.momentum import monthly_return_panel
from jegadeesh_titman_india.momentum import overlapping_strategy
from jegadeesh_titman_india.momentum import strategy_grid
from jegadeesh_titman_india.momentum import universe_filter


class SyntheticMarket:
    """A made-up market of shares whose daily returns are chosen by the test."""

    def __init__(self, share_count: int, month_count: int, days_per_month: int = 20):
        """Initialises a market with weekday trading dates and no returns yet.

        Args:
            share_count: The int number of shares.
            month_count: The int number of calendar months, starting in January 2020.
            days_per_month: The int number of trading days used in each month.

        Raises:
            Nothing.
        """
        self.symbols = []
        for share_number in range(share_count):
            self.symbols.append(f'SHARE{share_number:03d}')
        self.dates = []
        for month in pd.period_range('2020-01', periods=month_count, freq='M'):
            month_days = pd.bdate_range(month.start_time, month.end_time)[:days_per_month]
            self.dates.extend(month_days)
        self.returns = np.zeros((len(self.dates), share_count))

    def daily_panel(self) -> pd.DataFrame:
        """Gives the market as the long daily panel the study reads.

        Returns:
            A pandas.DataFrame with `date`, `symbol`, `close`, `daily_return` and `traded_value` columns.

        Raises:
            Nothing.
        """
        frame = pd.DataFrame(self.returns, index=pd.DatetimeIndex(self.dates), columns=self.symbols)
        long_frame = frame.stack().rename('daily_return').reset_index()
        long_frame.columns = [
            'date',
            'symbol',
            'daily_return',
        ]
        long_frame['close'] = 100.0
        long_frame['traded_value'] = 1000000.0
        return long_frame


class TestMonthlyReturnPanel:
    """Tests of MonthlyReturnPanel."""

    def test_monthly_returns_compound_daily_returns(self):
        """Checks that two daily gains of 10 percent compound to 21 percent in the month.

        Returns:
            None.

        Raises:
            AssertionError: The monthly return is wrong.
        """
        market = SyntheticMarket(share_count=1, month_count=2)
        market.returns[0, 0] = 0.10
        market.returns[1, 0] = 0.10
        panel = monthly_return_panel.MonthlyReturnPanel(market.daily_panel())
        assert panel.monthly_returns.iloc[0, 0] == pytest.approx(0.21)
        assert panel.monthly_returns.iloc[1, 0] == pytest.approx(0.0)

    def test_skipped_days_leave_out_the_end_of_the_month(self):
        """Checks that a gain in the last five trading days counts without the skip and not with it.

        Returns:
            None.

        Raises:
            AssertionError: The ranking returns are wrong.
        """
        market = SyntheticMarket(share_count=1, month_count=3)
        last_day_of_second_month = 39
        market.returns[last_day_of_second_month, 0] = 0.50
        panel = monthly_return_panel.MonthlyReturnPanel(market.daily_panel())
        without_skip = panel.ranking_returns(ranking_months=1, skipped_days=0)
        with_skip = panel.ranking_returns(ranking_months=1, skipped_days=5)
        assert without_skip.iloc[1, 0] == pytest.approx(0.50)
        assert with_skip.iloc[1, 0] == pytest.approx(0.0)


class TestDecileRanker:
    """Tests of DecileRanker."""

    def test_twenty_shares_make_ten_deciles_of_two(self):
        """Checks that twenty ranked shares fill each decile with two shares, lowest returns in decile 1.

        Returns:
            None.

        Raises:
            AssertionError: The deciles are wrong.
        """
        ranking_returns = pd.DataFrame([np.arange(20, dtype=float)])
        eligible = pd.DataFrame([np.ones(20, dtype=bool)])
        deciles = decile_ranker.DecileRanker().assign(ranking_returns, eligible)
        assert list(np.bincount(deciles[0])[1:]) == [2] * 10
        assert deciles[0, 0] == 1
        assert deciles[0, 19] == 10

    def test_ineligible_shares_are_not_ranked(self):
        """Checks that a share marked ineligible gets decile 0.

        Returns:
            None.

        Raises:
            AssertionError: The ineligible share was ranked.
        """
        ranking_returns = pd.DataFrame([np.arange(11, dtype=float)])
        eligible = pd.DataFrame([[True] * 10 + [False]])
        deciles = decile_ranker.DecileRanker().assign(ranking_returns, eligible)
        assert deciles[0, 10] == 0


class TestOverlappingStrategy:
    """Tests of OverlappingStrategy."""

    def test_each_cohort_carries_one_kth_of_the_weight(self):
        """Checks that with K of 3, a share in only one of the three cohorts held has weight one third of its cohort weight.

        Returns:
            None.

        Raises:
            AssertionError: The weights are wrong.
        """
        monthly_returns = pd.DataFrame(np.zeros((4, 20)))
        deciles = np.zeros((4, 20), dtype=int)
        for month_position in range(3):
            deciles[month_position] = np.repeat(np.arange(1, 11), 2)
        deciles[0, 18] = 9
        deciles[0, 17] = 10
        strategy = overlapping_strategy.OverlappingStrategy(monthly_returns, deciles, holding_months=3)
        weights = strategy.decile_weights(10)
        assert weights[3].sum() == pytest.approx(1.0)
        assert weights[3, 18] == pytest.approx(2.0 / 3.0 / 2.0)
        assert weights[3, 17] == pytest.approx(1.0 / 3.0 / 2.0)

    def test_planted_momentum_gives_positive_spread(self):
        """Checks that shares whose good and bad runs persist give winners minus losers a positive return.

        Returns:
            None.

        Raises:
            AssertionError: The spread is not positive.
        """
        market = SyntheticMarket(share_count=50, month_count=24)
        random_generator = np.random.default_rng(1)
        drift = np.linspace(-0.002, 0.002, 50)
        market.returns = drift + random_generator.normal(0.0, 0.01, market.returns.shape)
        panel = monthly_return_panel.MonthlyReturnPanel(market.daily_panel())
        grid = strategy_grid.StrategyGrid(panel, universe_filter.UniverseFilter(panel))
        returns = grid.build(ranking_months=6, holding_months=6, skipped_days=0).decile_returns()
        assert returns['winners_minus_losers'].mean() > 0.03

    def test_turnover_is_full_purchase_then_zero_for_unchanged_holdings(self):
        """Checks that a portfolio whose members never change is bought once and then barely traded.

        Returns:
            None.

        Raises:
            AssertionError: The turnover is wrong.
        """
        monthly_returns = pd.DataFrame(np.zeros((5, 20)))
        deciles = np.tile(np.repeat(np.arange(1, 11), 2), (5, 1))
        strategy = overlapping_strategy.OverlappingStrategy(monthly_returns, deciles, holding_months=2)
        bought, sold = strategy.turnover(10)
        assert bought.iloc[2] == pytest.approx(1.0)
        assert bought.iloc[3] == pytest.approx(0.0)
        assert sold.iloc[3] == pytest.approx(0.0)


class TestCosts:
    """Tests of IndianTransactionCosts."""

    def test_rates_match_a_hand_calculation(self):
        """Checks the buy and sell rates against the charges added up by hand.

        Returns:
            None.

        Raises:
            AssertionError: A rate is wrong.
        """
        costs = indian_transaction_costs.IndianTransactionCosts(impact_cost=0.001)
        fees_with_tax = (0.0000297 + 0.000001) * 1.18
        assert costs.sell_rate() == pytest.approx(0.001 + fees_with_tax + 0.001)
        assert costs.buy_rate() == pytest.approx(0.001 + fees_with_tax + 0.001 + 0.00015)


class TestFilterAndCalendar:
    """Tests of ImplausibleMoveFilter and CalendarMonthStudy."""

    def test_filter_zeroes_only_implausible_moves(self):
        """Checks that a 90 percent fall is set to zero and a 15 percent fall is kept.

        Returns:
            None.

        Raises:
            AssertionError: The wrong rows were changed.
        """
        panel = pd.DataFrame(
            {
                'symbol': [
                    'A',
                    'B',
                ],
                'date': [
                    pd.Timestamp('2020-01-02'),
                    pd.Timestamp('2020-01-02'),
                ],
                'daily_return': [
                    -0.9,
                    -0.15,
                ],
            }
        )
        move_filter = implausible_move_filter.ImplausibleMoveFilter()
        cleaned = move_filter.clean(panel)
        assert list(cleaned['daily_return']) == [0.0, -0.15]
        assert len(move_filter.removed_rows) == 1

    def test_calendar_table_separates_march(self):
        """Checks that the March row averages only March returns.

        Returns:
            None.

        Raises:
            AssertionError: The March mean is wrong.
        """
        months = pd.period_range('2020-01', periods=24, freq='M')
        returns = pd.Series(0.01, index=months)
        returns[returns.index.month == 3] = -0.05
        table = calendar_month_study.CalendarMonthStudy().table(returns)
        assert table.loc[3, 'mean'] == pytest.approx(-0.05)
        assert table.loc[4, 'mean'] == pytest.approx(0.01)
