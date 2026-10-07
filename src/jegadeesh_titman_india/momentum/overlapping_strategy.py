"""The paper's J-month/K-month strategy with overlapping holding periods.

Each month a new set of deciles is formed and held for K months, so in any month the strategy holds K cohorts, each with 1/K of the money. Within a cohort, shares are equally weighted and rebalanced monthly, which is the version the paper reports.

Typical usage example:

  strategy = OverlappingStrategy(monthly_returns, deciles, holding_months=6)
  returns = strategy.decile_returns()
  buys, sells = strategy.turnover(decile=10)
"""

import numpy as np
import pandas as pd


DECILE_COUNT = 10

LOSERS = 1

WINNERS = 10


class OverlappingStrategy:
    """A set of overlapping decile portfolios held for K months each.

    Attributes:
        monthly_returns: A pandas.DataFrame of monthly returns, months by symbols.
        deciles: A numpy.ndarray of ints with the same shape, the decile each share was put in at the end of each month, or 0 when it was not ranked.
        holding_months: The int number of months, K in the paper, each cohort is held.
    """

    def __init__(self, monthly_returns: pd.DataFrame, deciles: np.ndarray, holding_months: int):
        """Initialises the strategy.

        Args:
            monthly_returns: A pandas.DataFrame of monthly returns, months by symbols.
            deciles: A numpy.ndarray of ints with the same shape, holding each share's decile at each formation month, or 0.
            holding_months: The int number of months, K in the paper, each cohort is held.

        Raises:
            ValueError: The shapes differ or holding_months is less than 1.
        """
        if monthly_returns.shape != deciles.shape:
            raise ValueError(f'Shapes differ: {monthly_returns.shape=} {deciles.shape=}')
        if holding_months < 1:
            raise ValueError(f'holding_months must be at least 1: {holding_months=}')
        self.monthly_returns = monthly_returns
        self.deciles = deciles
        self.holding_months = holding_months
        self._return_values = monthly_returns.to_numpy()
        self._cohort_formed = (deciles > 0).any(axis=1)

    def decile_returns(self) -> pd.DataFrame:
        """Gives the monthly return of each decile portfolio and of winners minus losers.

        A month has a return only when all K cohorts that should be held in it were formed.

        Returns:
            A pandas.DataFrame indexed by month, with columns 1 to 10 for the deciles and `winners_minus_losers` for decile 10 minus decile 1, NaN in months without a full set of cohorts.

        Raises:
            Nothing.
        """
        month_count = len(self.monthly_returns)
        result = np.full((month_count, DECILE_COUNT), np.nan)
        for month_position in range(month_count):
            if not self._full_set_of_cohorts(month_position):
                continue
            cohort_means = []
            for cohort_position in range(month_position - self.holding_months, month_position):
                cohort_means.append(self._cohort_decile_means(cohort_position, month_position))
            result[month_position] = np.mean(cohort_means, axis=0)
        columns = list(range(1, DECILE_COUNT + 1))
        frame = pd.DataFrame(result, index=self.monthly_returns.index, columns=columns)
        frame['winners_minus_losers'] = frame[WINNERS] - frame[LOSERS]
        return frame

    def decile_weights(self, decile: int) -> np.ndarray:
        """Gives the weight of every share in one decile portfolio at the start of each month.

        Args:
            decile: The int decile, 1 for losers to 10 for winners.

        Returns:
            A numpy.ndarray of floats, months by symbols, each row summing to 1 in months with a full set of cohorts and to 0 otherwise.

        Raises:
            ValueError: decile is not between 1 and 10.
        """
        if decile < 1 or decile > DECILE_COUNT:
            raise ValueError(f'Not a decile: {decile=}')
        weights = np.zeros(self._return_values.shape)
        for month_position in range(len(weights)):
            if not self._full_set_of_cohorts(month_position):
                continue
            traded = ~np.isnan(self._return_values[month_position])
            for cohort_position in range(month_position - self.holding_months, month_position):
                members = (self.deciles[cohort_position] == decile) & traded
                member_count = members.sum()
                if member_count > 0:
                    weights[month_position, members] += 1.0 / member_count / self.holding_months
        return weights

    def next_month_weights(self, decile: int) -> pd.Series:
        """Gives the weight of every share in one decile portfolio for the month after the data ends, which is what a live portfolio should hold.

        The K most recent formation months, including the last month of data, each contribute 1/K, split equally among their members that traded in the last month.

        Args:
            decile: The int decile, 1 for losers to 10 for winners.

        Returns:
            A pandas.Series of weights indexed by symbol, holding only shares with a weight above zero and summing to 1.

        Raises:
            ValueError: decile is not between 1 and 10, or the last K months did not all form a cohort.
        """
        if decile < 1 or decile > DECILE_COUNT:
            raise ValueError(f'Not a decile: {decile=}')
        month_count = len(self._return_values)
        first_cohort = month_count - self.holding_months
        if first_cohort < 0 or not self._cohort_formed[first_cohort:].all():
            raise ValueError(f'Not enough formed cohorts for the next month: {self.holding_months=}')
        traded_last_month = ~np.isnan(self._return_values[-1])
        weights = np.zeros(self._return_values.shape[1])
        for cohort_position in range(first_cohort, month_count):
            members = (self.deciles[cohort_position] == decile) & traded_last_month
            member_count = members.sum()
            if member_count > 0:
                weights[members] += 1.0 / member_count / self.holding_months
        series = pd.Series(weights, index=self.monthly_returns.columns)
        series = series[series > 0]
        return series / series.sum()

    def turnover(self, decile: int) -> tuple[pd.Series, pd.Series]:
        """Gives the fraction of one decile portfolio bought and sold at the start of each month.

        Weights drift with last month's returns before being rebalanced back to target, and a share that stopped trading is taken as sold at no cost.

        Args:
            decile: The int decile, 1 for losers to 10 for winners.

        Returns:
            A tuple (bought, sold) of pandas.Series indexed by month, each the fraction of the portfolio's value traded on that side; the first month with a full set of cohorts counts as buying the whole portfolio.

        Raises:
            ValueError: decile is not between 1 and 10.
        """
        weights = self.decile_weights(decile)
        bought = np.zeros(len(weights))
        sold = np.zeros(len(weights))
        for month_position in range(len(weights)):
            target = weights[month_position]
            if target.sum() == 0:
                continue
            if month_position == 0 or weights[month_position - 1].sum() == 0:
                bought[month_position] = target.sum()
                continue
            previous = weights[month_position - 1]
            previous_returns = np.nan_to_num(self._return_values[month_position - 1], nan=-1.0)
            drifted = previous * (1.0 + previous_returns)
            if drifted.sum() > 0:
                drifted = drifted / drifted.sum()
            change = target - drifted
            bought[month_position] = change[change > 0].sum()
            sold[month_position] = -change[change < 0].sum()
        index = self.monthly_returns.index
        return pd.Series(bought, index=index), pd.Series(sold, index=index)

    def _full_set_of_cohorts(self, month_position: int) -> bool:
        """Says whether all K cohorts to be held in a month were formed.

        Args:
            month_position: The int row position of the holding month.

        Returns:
            A bool that is True when every one of the previous K months formed a cohort.

        Raises:
            Nothing.
        """
        first_cohort = month_position - self.holding_months
        if first_cohort < 0:
            return False
        return bool(self._cohort_formed[first_cohort:month_position].all())

    def _cohort_decile_means(self, cohort_position: int, month_position: int) -> np.ndarray:
        """Gives the equally weighted return of each decile of one cohort in one month.

        Args:
            cohort_position: The int row position of the month the cohort was formed.
            month_position: The int row position of the holding month.

        Returns:
            A numpy.ndarray of 10 floats, NaN for a decile none of whose shares traded that month.

        Raises:
            Nothing.
        """
        returns = self._return_values[month_position]
        cohort_deciles = self.deciles[cohort_position]
        usable = (cohort_deciles > 0) & ~np.isnan(returns)
        sums = np.bincount(cohort_deciles[usable], weights=returns[usable], minlength=DECILE_COUNT + 1)
        counts = np.bincount(cohort_deciles[usable], minlength=DECILE_COUNT + 1)
        with np.errstate(invalid='ignore', divide='ignore'):
            means = sums / counts
        means[counts == 0] = np.nan
        return means[1:]
