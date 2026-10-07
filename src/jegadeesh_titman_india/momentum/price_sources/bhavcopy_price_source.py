"""Daily NSE share total returns from parsed bhavcopy files, including shares that were later delisted.

Bhavcopy prices are not adjusted, and NSE does not adjust the previous close either, so splits, bonuses and dividends are applied from NSE's list of corporate actions. On the first trading day on or after an ex-date, the return is the close times the price factor plus the dividend, divided by the previous close, minus one.

A share can move between the normal `EQ` series and the trade-for-trade `BE` and `BZ` series, so all three are kept, preferring `EQ` when a share appears in more than one on the same day.

Typical usage example:

  source = BhavcopyPriceSource(store_directory, corporate_actions_directory)
  daily_panel = source.daily_panel()
  print(source.adjustment_report)
"""

import logging
import pathlib

import numpy as np
import pandas as pd

from jegadeesh_titman_india.bhavcopy import bhavcopy_store
from jegadeesh_titman_india.bhavcopy import corporate_action_parser


SERIES_PREFERENCE = {
    'EQ': 0,
    'BE': 1,
    'BZ': 2,
}

LARGEST_DIVIDEND_FRACTION = 0.5

EX_DATE_DAYS_BEFORE = 7

EX_DATE_DAYS_AFTER = 10


class BhavcopyPriceSource:
    """Daily total returns and traded values of every NSE share in the bhavcopy archive.

    Attributes:
        store_directory: The pathlib.Path holding the yearly Parquet files.
        corporate_actions_directory: The pathlib.Path holding NSE's yearly corporate action files.
        adjustment_report: A dict of int counts describing the corporate actions applied by the last call to daily_panel, or None before the first call.
    """

    def __init__(self, store_directory: pathlib.Path, corporate_actions_directory: pathlib.Path):
        """Initialises the source.

        Args:
            store_directory: The pathlib.Path holding the yearly Parquet files.
            corporate_actions_directory: The pathlib.Path holding NSE's yearly corporate action files.

        Raises:
            Nothing.
        """
        self.store_directory = store_directory
        self.corporate_actions_directory = corporate_actions_directory
        self.adjustment_report = None

    def daily_panel(self) -> pd.DataFrame:
        """Reads the stored rows as one row per share per trading day, with returns adjusted for corporate actions.

        Returns:
            A pandas.DataFrame with `date`, `symbol`, `close`, `daily_return` and `traded_value` columns, sorted by symbol and date.

        Raises:
            FileNotFoundError: The bhavcopy store has not been built.
        """
        rows = self._share_rows()
        adjustments = self._adjustments_by_trading_day(rows)
        rows = rows.merge(
            adjustments,
            on=[
                'symbol',
                'date',
            ],
            how='left',
        )
        rows['price_factor'] = rows['price_factor'].fillna(1.0)
        rows['dividend'] = rows['dividend'].fillna(0.0)
        valid_previous_close = rows['previous_close'] > 0
        unadjusted_return = rows['close'] / rows['previous_close'] - 1.0
        adjusted_close = rows['close'] * rows['price_factor']
        factor_return = adjusted_close / rows['previous_close'] - 1.0
        factor_helps = np.abs(np.log1p(factor_return)) < np.abs(np.log1p(unadjusted_return))
        use_factor = (rows['price_factor'] != 1.0) & factor_helps
        dividend_plausible = rows['dividend'] <= LARGEST_DIVIDEND_FRACTION * rows['previous_close']
        use_dividend = (rows['dividend'] > 0) & dividend_plausible
        price_part = rows['close'].where(~use_factor, adjusted_close)
        dividend_part = rows['dividend'].where(use_dividend, 0.0)
        rows['daily_return'] = ((price_part + dividend_part) / rows['previous_close'] - 1.0).where(valid_previous_close)
        self.adjustment_report = {
            'share_count_changes_matched': int((rows['price_factor'] != 1.0).sum()),
            'share_count_changes_applied': int(use_factor.sum()),
            'dividends_matched': int((rows['dividend'] > 0).sum()),
            'dividends_applied': int(use_dividend.sum()),
        }
        logging.info('Corporate actions: %s', self.adjustment_report)
        return rows[
            [
                'date',
                'symbol',
                'close',
                'daily_return',
                'traded_value',
            ]
        ].sort_values(
            [
                'symbol',
                'date',
            ]
        ).reset_index(drop=True)

    def _share_rows(self) -> pd.DataFrame:
        """Reads the stored rows and keeps one share-series row per share per day.

        Returns:
            A pandas.DataFrame with `date`, `symbol`, `close`, `previous_close` and `traded_value` columns.

        Raises:
            FileNotFoundError: The bhavcopy store has not been built.
        """
        store = bhavcopy_store.BhavcopyStore(raw_directory=self.store_directory, store_directory=self.store_directory)
        rows = store.read()
        rows = rows[rows['series'].isin(SERIES_PREFERENCE.keys())].copy()
        rows['date'] = rows['date'].astype('datetime64[ns]')
        rows['series_order'] = rows['series'].map(SERIES_PREFERENCE)
        rows = rows.sort_values(
            [
                'symbol',
                'date',
                'series_order',
            ]
        )
        rows = rows.drop_duplicates(
            subset=[
                'symbol',
                'date',
            ],
            keep='first',
        )
        return rows[
            [
                'date',
                'symbol',
                'close',
                'previous_close',
                'traded_value',
            ]
        ].reset_index(drop=True)

    def _adjustments_by_trading_day(self, rows: pd.DataFrame) -> pd.DataFrame:
        """Moves each corporate action to the share's first trading day on or after its ex-date and combines actions falling on the same day.

        Args:
            rows: A pandas.DataFrame of share rows with `symbol` and `date` columns.

        Returns:
            A pandas.DataFrame with `symbol`, `date`, `price_factor` and `dividend` columns, one row per share per trading day that has an action.

        Raises:
            OSError: A corporate action file cannot be read.
        """
        actions = corporate_action_parser.CorporateActionParser().parse_directory(self.corporate_actions_directory)
        actions['ex_date'] = actions['ex_date'].astype('datetime64[ns]')
        actions = actions.sort_values('ex_date').reset_index(drop=True)
        changes_share_count = actions['price_factor'] != 1.0
        trading_days = rows[
            [
                'symbol',
                'date',
            ]
        ].sort_values('date')
        dividends_only = pd.merge_asof(
            actions[~changes_share_count],
            trading_days,
            left_on='ex_date',
            right_on='date',
            by='symbol',
            direction='forward',
        )
        share_count_changes = self._match_share_count_changes(actions[changes_share_count], rows)
        matched = pd.concat(
            [
                dividends_only,
                share_count_changes,
            ],
            ignore_index=True,
        )
        matched = matched.dropna(subset=['date'])
        combined_rows = []
        for (symbol, date), group in matched.groupby(
            [
                'symbol',
                'date',
            ]
        ):
            combined_rows.append(
                {
                    'symbol': symbol,
                    'date': date,
                    'price_factor': float(group['price_factor'].prod()),
                    'dividend': float(group['dividend'].sum()),
                }
            )
        return pd.DataFrame(combined_rows)

    def _match_share_count_changes(self, actions: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
        """Puts each split, bonus or consolidation on the trading day near its listed ex-date whose price drop best fits its ratio.

        Actions listed for the same share and ex-date, such as a bonus and a split on one day, are first combined into one factor. NSE's list sometimes gives an ex-date a few days away from the day the price actually adjusted, so every trading day from a week before to ten days after the listed date is tried, and the one whose unadjusted return is closest to what the combined ratio implies is chosen.

        Args:
            actions: A pandas.DataFrame of parsed actions whose `price_factor` is not 1.
            rows: A pandas.DataFrame of share rows with `symbol`, `date`, `close` and `previous_close` columns.

        Returns:
            A pandas.DataFrame like actions with a `date` column added, one row per action that has a trading day in its window.

        Raises:
            Nothing.
        """
        combined_actions = []
        for (symbol, ex_date), group in actions.groupby(
            [
                'symbol',
                'ex_date',
            ]
        ):
            combined_actions.append(
                {
                    'symbol': symbol,
                    'ex_date': ex_date,
                    'price_factor': float(group['price_factor'].prod()),
                    'dividend': float(group['dividend'].sum()),
                }
            )
        actions = pd.DataFrame(combined_actions)
        actions['action_number'] = actions.index
        candidates = actions.merge(
            rows[
                [
                    'symbol',
                    'date',
                    'close',
                    'previous_close',
                ]
            ],
            on='symbol',
            how='inner',
        )
        window_start = candidates['ex_date'] - pd.Timedelta(days=EX_DATE_DAYS_BEFORE)
        window_end = candidates['ex_date'] + pd.Timedelta(days=EX_DATE_DAYS_AFTER)
        in_window = (candidates['date'] >= window_start) & (candidates['date'] <= window_end) & (candidates['previous_close'] > 0)
        candidates = candidates[in_window].copy()
        unadjusted_log_return = np.log(candidates['close'] / candidates['previous_close'])
        candidates['misfit'] = np.abs(unadjusted_log_return + np.log(candidates['price_factor']))
        best = candidates.sort_values('misfit').drop_duplicates(subset=['action_number'], keep='first')
        return best.drop(
            columns=[
                'close',
                'previous_close',
                'misfit',
                'action_number',
            ]
        )
