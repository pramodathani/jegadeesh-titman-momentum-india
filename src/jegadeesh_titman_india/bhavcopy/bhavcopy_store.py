"""Turns downloaded bhavcopy zip files into one Parquet file per year and reads them back.

Typical usage example:

  store = BhavcopyStore(raw_directory, store_directory)
  store.build()
  rows = store.read()
"""

import datetime
import logging
import pathlib

import pandas as pd

from jegadeesh_titman_india.bhavcopy import bhavcopy_downloader
from jegadeesh_titman_india.bhavcopy import legacy_bhavcopy_parser
from jegadeesh_titman_india.bhavcopy import udiff_bhavcopy_parser


class BhavcopyStore:
    """The yearly Parquet files holding every parsed bhavcopy row.

    Attributes:
        raw_directory: The pathlib.Path holding the downloaded zip files, one folder per year.
        store_directory: The pathlib.Path holding the yearly Parquet files.
    """

    def __init__(self, raw_directory: pathlib.Path, store_directory: pathlib.Path):
        """Initialises the store.

        Args:
            raw_directory: The pathlib.Path holding the downloaded zip files.
            store_directory: The pathlib.Path holding the yearly Parquet files.

        Raises:
            Nothing.
        """
        self.raw_directory = raw_directory
        self.store_directory = store_directory
        self._legacy_parser = legacy_bhavcopy_parser.LegacyBhavcopyParser()
        self._udiff_parser = udiff_bhavcopy_parser.UdiffBhavcopyParser()

    def build(self) -> dict:
        """Parses every downloaded year and writes one Parquet file for each.

        Returns:
            A dict mapping each int year to the int number of rows written.

        Raises:
            OSError: A file cannot be read or written.
        """
        self.store_directory.mkdir(parents=True, exist_ok=True)
        row_counts = {}
        year_directories = sorted(path for path in self.raw_directory.iterdir() if path.is_dir())
        for year_directory in year_directories:
            frames = []
            for file_path in sorted(year_directory.glob('*.csv.zip')):
                trading_date = datetime.date.fromisoformat(file_path.name.removesuffix('.csv.zip'))
                frames.append(self._parse(file_path, trading_date))
            if not frames:
                continue
            year_rows = pd.concat(frames, ignore_index=True)
            year_rows.to_parquet(self.store_directory / f'{year_directory.name}.parquet', index=False)
            row_counts[int(year_directory.name)] = len(year_rows)
            logging.info('Stored %s rows for %s', len(year_rows), year_directory.name)
        return row_counts

    def read(self) -> pd.DataFrame:
        """Reads every stored year into one frame.

        Returns:
            A pandas.DataFrame with `date`, `symbol`, `series`, `close`, `previous_close`, `traded_value` and `isin` columns.

        Raises:
            FileNotFoundError: build has not been run.
        """
        file_paths = sorted(self.store_directory.glob('*.parquet'))
        if not file_paths:
            raise FileNotFoundError(f'No stored bhavcopy years in {self.store_directory}')
        frames = []
        for file_path in file_paths:
            frames.append(pd.read_parquet(file_path))
        return pd.concat(frames, ignore_index=True)

    def _parse(self, file_path: pathlib.Path, trading_date: datetime.date) -> pd.DataFrame:
        """Parses one file with the parser for the format NSE used that day.

        Args:
            file_path: The pathlib.Path of the zipped CSV file.
            trading_date: The datetime.date the file is for.

        Returns:
            A pandas.DataFrame of the day's rows in the standard columns.

        Raises:
            OSError: The file cannot be read.
        """
        if trading_date <= bhavcopy_downloader.LAST_LEGACY_DATE:
            return self._legacy_parser.parse(file_path, trading_date)
        return self._udiff_parser.parse(file_path, trading_date)
