"""Means, t-statistics and market-model regressions for monthly return series.

Plain t-statistics are used for non-overlapping monthly returns, as in the paper's Tables I to IV, and Newey-West t-statistics for series that overlap, as for the paper's cumulative event-time returns.

Typical usage example:

  statistics = ReturnStatistics()
  mean, t_statistic = statistics.mean_and_t(monthly_returns)
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm


class ReturnStatistics:
    """Statistical tests applied to the study's return series."""

    def mean_and_t(self, returns: pd.Series) -> tuple[float, float]:
        """Gives the mean of a return series and its ordinary t-statistic against zero.

        Args:
            returns: A pandas.Series of returns, where NaN values are ignored.

        Returns:
            A tuple (mean, t_statistic) of floats, both NaN when fewer than two returns are present.

        Raises:
            Nothing.
        """
        present = returns.dropna()
        if len(present) < 2:
            return np.nan, np.nan
        standard_error = present.std(ddof=1) / np.sqrt(len(present))
        if standard_error == 0:
            return float(present.mean()), np.nan
        return float(present.mean()), float(present.mean() / standard_error)

    def newey_west_mean_and_t(self, returns: pd.Series, lags: int) -> tuple[float, float]:
        """Gives the mean of a serially correlated series and its Newey-West t-statistic against zero.

        Args:
            returns: A pandas.Series of returns, where NaN values are ignored.
            lags: The int number of lags in the Newey-West covariance estimate.

        Returns:
            A tuple (mean, t_statistic) of floats, both NaN when fewer than three returns are present.

        Raises:
            Nothing.
        """
        present = returns.dropna()
        if len(present) < 3:
            return np.nan, np.nan
        constant = np.ones(len(present))
        fitted = sm.OLS(present.to_numpy(), constant).fit(cov_type='HAC', cov_kwds={'maxlags': lags})
        return float(fitted.params[0]), float(fitted.tvalues[0])

    def market_model(self, portfolio_returns: pd.Series, market_returns: pd.Series) -> dict:
        """Regresses portfolio returns on market returns to get alpha and beta.

        No risk-free rate is subtracted, because none is available in the study's data; for a zero-cost portfolio this makes no difference.

        Args:
            portfolio_returns: A pandas.Series of monthly portfolio returns.
            market_returns: A pandas.Series of monthly market returns with the same kind of index.

        Returns:
            A dict with float `alpha`, `alpha_t`, `beta`, `beta_t` and int `months`, the floats NaN when fewer than three months overlap.

        Raises:
            Nothing.
        """
        joined = pd.concat(
            [
                portfolio_returns.rename('portfolio'),
                market_returns.rename('market'),
            ],
            axis=1,
        ).dropna()
        if len(joined) < 3:
            return {
                'alpha': np.nan,
                'alpha_t': np.nan,
                'beta': np.nan,
                'beta_t': np.nan,
                'months': len(joined),
            }
        explanatory = sm.add_constant(joined['market'].to_numpy())
        fitted = sm.OLS(joined['portfolio'].to_numpy(), explanatory).fit()
        return {
            'alpha': float(fitted.params[0]),
            'alpha_t': float(fitted.tvalues[0]),
            'beta': float(fitted.params[1]),
            'beta_t': float(fitted.tvalues[1]),
            'months': len(joined),
        }
