"""Follows winners-minus-losers returns for up to 36 months after each formation date, as in the paper's Table VII.

Typical usage example:

  study = EventTimeStudy(monthly_returns, deciles)
  table = study.table(horizon_months=36)
"""

import numpy as np
import pandas as pd

from jegadeesh_titman_india.momentum import overlapping_strategy
from jegadeesh_titman_india.momentum import return_statistics


MONTHLY_NEWEY_WEST_LAGS = 6


class EventTimeStudy:
    """The returns of each cohort's winners minus its losers in each month after it was formed.

    Attributes:
        monthly_returns: A pandas.DataFrame of monthly returns, months by symbols.
        deciles: A numpy.ndarray of ints with the same shape, holding each share's decile at each formation month, or 0.
    """

    def __init__(self, monthly_returns: pd.DataFrame, deciles: np.ndarray):
        """Initialises the study.

        Args:
            monthly_returns: A pandas.DataFrame of monthly returns, months by symbols.
            deciles: A numpy.ndarray of ints with the same shape, holding each share's decile at each formation month, or 0.

        Raises:
            ValueError: The shapes differ.
        """
        if monthly_returns.shape != deciles.shape:
            raise ValueError(f'Shapes differ: {monthly_returns.shape=} {deciles.shape=}')
        self.monthly_returns = monthly_returns
        self.deciles = deciles
        self._return_values = monthly_returns.to_numpy()

    def spreads(self, horizon_months: int) -> pd.DataFrame:
        """Gives each cohort's winners-minus-losers return in each month after formation.

        Args:
            horizon_months: The int number of months after formation to follow.

        Returns:
            A pandas.DataFrame indexed by formation month, with columns 1 to horizon_months, NaN where the month is beyond the data.

        Raises:
            Nothing.
        """
        month_count = len(self._return_values)
        result = np.full((month_count, horizon_months), np.nan)
        for formation_position in range(month_count):
            cohort_deciles = self.deciles[formation_position]
            winners = cohort_deciles == overlapping_strategy.WINNERS
            losers = cohort_deciles == overlapping_strategy.LOSERS
            if not winners.any() or not losers.any():
                continue
            for horizon in range(1, horizon_months + 1):
                month_position = formation_position + horizon
                if month_position >= month_count:
                    break
                returns = self._return_values[month_position]
                winner_returns = returns[winners]
                loser_returns = returns[losers]
                winner_returns = winner_returns[~np.isnan(winner_returns)]
                loser_returns = loser_returns[~np.isnan(loser_returns)]
                if len(winner_returns) == 0 or len(loser_returns) == 0:
                    continue
                result[formation_position, horizon - 1] = winner_returns.mean() - loser_returns.mean()
        columns = list(range(1, horizon_months + 1))
        return pd.DataFrame(result, index=self.monthly_returns.index, columns=columns)

    def table(self, horizon_months: int = 36) -> pd.DataFrame:
        """Summarises the average monthly and cumulative winners-minus-losers return in event time.

        Monthly t-statistics use Newey-West errors with 6 lags, because neighbouring cohorts share most of their shares; cumulative t-statistics use as many lags as months accumulated.

        Args:
            horizon_months: The int number of months after formation to follow.

        Returns:
            A pandas.DataFrame indexed by event month, with `monthly_mean`, `monthly_t`, `cumulative_mean`, `cumulative_t` and `cohorts` columns.

        Raises:
            Nothing.
        """
        statistics = return_statistics.ReturnStatistics()
        spreads = self.spreads(horizon_months)
        rows = []
        for horizon in range(1, horizon_months + 1):
            monthly = spreads[horizon]
            complete = spreads.loc[:, 1:horizon].dropna()
            cumulative = complete.sum(axis=1)
            monthly_mean, monthly_t = statistics.newey_west_mean_and_t(monthly, MONTHLY_NEWEY_WEST_LAGS)
            cumulative_mean, cumulative_t = statistics.newey_west_mean_and_t(cumulative, horizon)
            rows.append(
                {
                    'event_month': horizon,
                    'monthly_mean': monthly_mean,
                    'monthly_t': monthly_t,
                    'cumulative_mean': cumulative_mean,
                    'cumulative_t': cumulative_t,
                    'cohorts': int(monthly.notna().sum()),
                }
            )
        return pd.DataFrame(rows).set_index('event_month')
