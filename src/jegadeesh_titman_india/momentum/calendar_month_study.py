"""Averages a strategy's returns by calendar month, as in the paper's Tables IV and V.

In the US the paper found a large January loss, which it linked to tax-loss selling. India's tax year ends on 31 March, so March is the month to watch here.

Typical usage example:

  study = CalendarMonthStudy()
  table = study.table(winners_minus_losers_returns)
"""

import pandas as pd

from jegadeesh_titman_india.momentum import return_statistics


class CalendarMonthStudy:
    """The summary of a monthly return series split by calendar month."""

    def table(self, returns: pd.Series) -> pd.DataFrame:
        """Gives the mean, t-statistic and share of positive months for each calendar month.

        Args:
            returns: A pandas.Series of monthly returns indexed by a monthly pandas.PeriodIndex.

        Returns:
            A pandas.DataFrame indexed by calendar month number 1 to 12, with `mean`, `t_statistic`, `fraction_positive` and `years` columns, plus a row named `all` for the whole series.

        Raises:
            AttributeError: returns is not indexed by monthly periods.
        """
        statistics = return_statistics.ReturnStatistics()
        present = returns.dropna()
        rows = []
        for calendar_month in range(1, 13):
            series = present[present.index.month == calendar_month]
            mean, t_statistic = statistics.mean_and_t(series)
            rows.append(
                {
                    'calendar_month': calendar_month,
                    'mean': mean,
                    't_statistic': t_statistic,
                    'fraction_positive': float((series > 0).mean()) if len(series) else float('nan'),
                    'years': len(series),
                }
            )
        mean, t_statistic = statistics.mean_and_t(present)
        rows.append(
            {
                'calendar_month': 'all',
                'mean': mean,
                't_statistic': t_statistic,
                'fraction_positive': float((present > 0).mean()),
                'years': len(present),
            }
        )
        return pd.DataFrame(rows).set_index('calendar_month')
