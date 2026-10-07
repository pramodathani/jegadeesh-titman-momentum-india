"""Monthly returns, ranking-period returns and liquidity for every share, built from daily returns.

Daily returns are compounded into calendar-month returns, which is how the paper turned CRSP daily returns into monthly ones. Ranking-period returns can end a number of trading days before the month ends, which gives the paper's "skip a week" strategies.

Typical usage example:

  panel = MonthlyReturnPanel(daily_panel)
  six_month_returns = panel.ranking_returns(ranking_months=6, skipped_days=0)
"""

import numpy as np
import pandas as pd


class MonthlyReturnPanel:
    """Every share's returns and traded value, arranged as one row per calendar month and one column per share.

    Attributes:
        months: A pandas.PeriodIndex of the calendar months covered, in order.
        symbols: A pandas.Index of the share symbols, one per column.
        monthly_returns: A pandas.DataFrame of compounded monthly returns, months by symbols, NaN where a share did not trade that month.
        traded_value: A pandas.DataFrame of each share's median daily traded value in rupees, months by symbols.
    """

    def __init__(self, daily_panel: pd.DataFrame):
        """Builds the monthly arrays from daily rows.

        Args:
            daily_panel: A pandas.DataFrame with `date`, `symbol`, `daily_return` and `traded_value` columns, one row per share per trading day.

        Raises:
            KeyError: A required column is missing.
        """
        daily_returns = daily_panel.pivot(index='date', columns='symbol', values='daily_return').sort_index()
        daily_traded_value = daily_panel.pivot(index='date', columns='symbol', values='traded_value').sort_index()
        traded = daily_traded_value.notna()
        growth = (1.0 + daily_returns.fillna(0.0))
        self._wealth = growth.cumprod()
        self._trading_dates = daily_returns.index
        month_of_day = self._trading_dates.to_period('M')
        self.months = pd.PeriodIndex(month_of_day.unique(), freq='M')
        self.symbols = daily_returns.columns
        compounded = growth.groupby(month_of_day).prod() - 1.0
        traded_in_month = traded.groupby(month_of_day).any()
        self.monthly_returns = compounded.where(traded_in_month)
        self.traded_value = daily_traded_value.groupby(month_of_day).median()
        self._month_end_positions = self._last_position_in_each_month(month_of_day)

    def ranking_returns(self, ranking_months: int, skipped_days: int) -> pd.DataFrame:
        """Gives each share's compounded return over the ranking period ending at each month's formation date.

        The ranking period for formation month t runs from the last trading day of month t minus ranking_months to the last trading day of month t, moved back by skipped_days trading days.

        Args:
            ranking_months: The int number of months, J in the paper, over which past returns are measured.
            skipped_days: The int number of trading days left out between the end of the ranking period and the start of the holding period.

        Returns:
            A pandas.DataFrame of ranking returns, months by symbols, NaN for months too early to have a full ranking period.

        Raises:
            ValueError: ranking_months is less than 1 or skipped_days is negative.
        """
        if ranking_months < 1:
            raise ValueError(f'ranking_months must be at least 1: {ranking_months=}')
        if skipped_days < 0:
            raise ValueError(f'skipped_days must not be negative: {skipped_days=}')
        wealth_values = self._wealth.to_numpy()
        result = np.full((len(self.months), len(self.symbols)), np.nan)
        for month_position in range(ranking_months, len(self.months)):
            start_position = self._month_end_positions[month_position - ranking_months]
            end_position = self._month_end_positions[month_position] - skipped_days
            if end_position <= start_position:
                continue
            result[month_position] = wealth_values[end_position] / wealth_values[start_position] - 1.0
        return pd.DataFrame(result, index=self.months, columns=self.symbols)

    def traded_in_every_month(self, ranking_months: int) -> pd.DataFrame:
        """Says whether each share traded in each of the ranking_months months up to and including each month.

        Args:
            ranking_months: The int number of months, J in the paper, that must all have a return.

        Returns:
            A pandas.DataFrame of bools, months by symbols.

        Raises:
            ValueError: ranking_months is less than 1.
        """
        if ranking_months < 1:
            raise ValueError(f'ranking_months must be at least 1: {ranking_months=}')
        has_return = self.monthly_returns.notna().astype(float)
        return has_return.rolling(ranking_months).sum() == ranking_months

    def trailing_traded_value(self, months: int = 6) -> pd.DataFrame:
        """Gives each share's average monthly median daily traded value over the last few months.

        Args:
            months: The int number of months to average over.

        Returns:
            A pandas.DataFrame of rupee traded values, months by symbols.

        Raises:
            Nothing.
        """
        return self.traded_value.rolling(months, min_periods=1).mean()

    def equal_weighted_market_returns(self) -> pd.Series:
        """Gives the average monthly return of every share that traded in the month.

        Returns:
            A pandas.Series of monthly returns indexed by month.

        Raises:
            Nothing.
        """
        return self.monthly_returns.mean(axis=1)

    def _last_position_in_each_month(self, month_of_day: pd.PeriodIndex) -> list[int]:
        """Finds the row position of the last trading day of each month.

        Args:
            month_of_day: A pandas.PeriodIndex giving the month of every trading date.

        Returns:
            A list of int row positions, one per month in self.months.

        Raises:
            Nothing.
        """
        positions = []
        month_codes = np.asarray(month_of_day.asi8)
        for month in self.months:
            matching = np.nonzero(month_codes == month.ordinal)[0]
            positions.append(int(matching[-1]))
        return positions
