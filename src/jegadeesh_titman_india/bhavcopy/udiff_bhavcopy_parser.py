"""Reads NSE's UDiFF bhavcopy format, used from 8 July 2024.

The file covers every cash-market instrument with ISO-style column names such as `TckrSymb`, `SctySrs`, `ClsPric` and `PrvsClsgPric`; only rows whose `FinInstrmTp` is `STK` are shares.

Typical usage example:

  rows = UdiffBhavcopyParser().parse(pathlib.Path('2025-01-02.csv.zip'), datetime.date(2025, 1, 2))
"""

import datetime
import pathlib

import pandas as pd


COLUMN_NAMES = {
    'TckrSymb': 'symbol',
    'SctySrs': 'series',
    'ClsPric': 'close',
    'PrvsClsgPric': 'previous_close',
    'TtlTrfVal': 'traded_value',
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

SHARE_INSTRUMENT_TYPE = 'STK'


class UdiffBhavcopyParser:
    """The reader for one zipped bhavcopy file in NSE's UDiFF format."""

    def parse(self, file_path: pathlib.Path, trading_date: datetime.date) -> pd.DataFrame:
        """Reads one day's file into the study's standard columns, keeping only shares.

        Args:
            file_path: The pathlib.Path of the zipped CSV file.
            trading_date: The datetime.date the file is for.

        Returns:
            A pandas.DataFrame with `date`, `symbol`, `series`, `close`, `previous_close`, `traded_value` and `isin` columns.

        Raises:
            OSError: The file cannot be read.
            KeyError: The file lacks a required column.
        """
        frame = pd.read_csv(file_path, compression='zip', dtype={'TckrSymb': str, 'SctySrs': str})
        frame.columns = [column.strip() for column in frame.columns]
        frame = frame[frame['FinInstrmTp'] == SHARE_INSTRUMENT_TYPE]
        frame = frame.rename(columns=COLUMN_NAMES)
        frame['date'] = pd.Timestamp(trading_date)
        frame['symbol'] = frame['symbol'].str.strip()
        frame['series'] = frame['series'].str.strip()
        return frame[OUTPUT_COLUMNS]
