"""Reads NSE's older bhavcopy format, used from 1994 until 5 July 2024.

The file has `SYMBOL, SERIES, OPEN, HIGH, LOW, CLOSE, LAST, PREVCLOSE, TOTTRDQTY, TOTTRDVAL, TIMESTAMP` columns, with `TOTALTRADES` and `ISIN` added in later years.

Typical usage example:

  rows = LegacyBhavcopyParser().parse(pathlib.Path('2005-01-03.csv.zip'), datetime.date(2005, 1, 3))
"""

import datetime
import pathlib

import pandas as pd


COLUMN_NAMES = {
    'SYMBOL': 'symbol',
    'SERIES': 'series',
    'CLOSE': 'close',
    'PREVCLOSE': 'previous_close',
    'TOTTRDVAL': 'traded_value',
    'ISIN': 'isin',
}

OUTPUT_COLUMNS = [
    'date',
    'symbol',
    'series',
    'close',
    'previous_close',
    'traded_value',
    'isin',
]


class LegacyBhavcopyParser:
    """The reader for one zipped bhavcopy file in NSE's older format."""

    def parse(self, file_path: pathlib.Path, trading_date: datetime.date) -> pd.DataFrame:
        """Reads one day's file into the study's standard columns.

        Args:
            file_path: The pathlib.Path of the zipped CSV file.
            trading_date: The datetime.date the file is for, taken from its name because older files write the date in several styles.

        Returns:
            A pandas.DataFrame with `date`, `symbol`, `series`, `close`, `previous_close`, `traded_value` and `isin` columns, where `isin` is empty in years before NSE added it.

        Raises:
            OSError: The file cannot be read.
            KeyError: The file lacks a required column.
        """
        frame = pd.read_csv(file_path, compression='zip', dtype={'SYMBOL': str, 'SERIES': str})
        frame.columns = [column.strip() for column in frame.columns]
        frame = frame.rename(columns=COLUMN_NAMES)
        if 'isin' not in frame.columns:
            frame['isin'] = None
        frame['date'] = pd.Timestamp(trading_date)
        frame['symbol'] = frame['symbol'].str.strip()
        frame['series'] = frame['series'].str.strip()
        return frame[OUTPUT_COLUMNS]
