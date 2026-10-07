"""Downloads NSE cash-market bhavcopy files from NSE's public archive.

A bhavcopy is NSE's end-of-day file listing every security traded that day with its open, high, low, close, previous close and traded value. NSE published one format up to 5 July 2024 and the UDiFF format from 8 July 2024, and the downloader picks the right address for each date.

Typical usage example:

  downloader = BhavcopyDownloader(
      directory=pathlib.Path('data/bhavcopy/raw'),
      start_date=datetime.date(1995, 1, 1),
      end_date=datetime.date(2026, 10, 6),
  )
  downloader.download_all()
"""

import datetime
import logging
import pathlib
import time

import requests


LAST_LEGACY_DATE = datetime.date(2024, 7, 5)

LEGACY_URL_TEMPLATE = 'https://nsearchives.nseindia.com/content/historical/EQUITIES/{year}/{month}/cm{day}{month}{year}bhav.csv.zip'

UDIFF_URL_TEMPLATE = 'https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{compact_date}_F_0000.csv.zip'

REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36',
    'Accept': '*/*',
    'Referer': 'https://www.nseindia.com/',
}

NOT_AVAILABLE_FILE_NAME = 'not_available.txt'

SATURDAY = 5


class BlockedByArchiveError(RuntimeError):
    """NSE's archive refused a request in a way that means scripted downloads are being blocked."""


class BhavcopyDownloader:
    """A resumable, throttled downloader of daily bhavcopy zip files for a range of dates.

    Attributes:
        directory: The pathlib.Path under which zip files are saved, one sub-folder per year.
        start_date: The datetime.date of the first day to download.
        end_date: The datetime.date of the last day to download.
        pause_seconds: The float number of seconds to wait after each request to the archive.
    """

    def __init__(
        self,
        directory: pathlib.Path,
        start_date: datetime.date,
        end_date: datetime.date,
        pause_seconds: float = 0.4,
    ):
        """Initialises the downloader.

        Args:
            directory: The pathlib.Path under which zip files are saved.
            start_date: The datetime.date of the first day to download.
            end_date: The datetime.date of the last day to download.
            pause_seconds: The float number of seconds to wait after each request.

        Raises:
            ValueError: start_date is after end_date.
        """
        if start_date > end_date:
            raise ValueError(f'start_date is after end_date: {start_date=} {end_date=}')
        self.directory = directory
        self.start_date = start_date
        self.end_date = end_date
        self.pause_seconds = pause_seconds
        self._session = requests.Session()
        self._session.headers.update(REQUEST_HEADERS)

    def download_all(self) -> dict:
        """Downloads every weekday in the range that is not already saved or known to be missing.

        Returns:
            A dict with int counts under `downloaded`, `already_saved`, `not_available` and `failed`.

        Raises:
            BlockedByArchiveError: The archive answered with HTTP 403 or 429 three times in a row.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        not_available_dates = self._read_not_available_dates()
        counts = {
            'downloaded': 0,
            'already_saved': 0,
            'not_available': 0,
            'failed': 0,
        }
        consecutive_refusals = 0
        trading_date = self.start_date
        while trading_date <= self.end_date:
            if trading_date.weekday() >= SATURDAY:
                trading_date = trading_date + datetime.timedelta(days=1)
                continue
            if self.file_path(trading_date).exists():
                counts['already_saved'] += 1
            elif trading_date in not_available_dates:
                counts['not_available'] += 1
            else:
                outcome = self._download_one(trading_date)
                if outcome == 'refused':
                    consecutive_refusals += 1
                    counts['failed'] += 1
                else:
                    consecutive_refusals = 0
                    counts[outcome] += 1
                if outcome == 'not_available':
                    self._record_not_available(trading_date)
                if consecutive_refusals >= 3:
                    raise BlockedByArchiveError(f'Archive refused three requests in a row, last on {trading_date=}')
                time.sleep(self.pause_seconds)
            if trading_date.day == 1 and trading_date.month == 1:
                logging.info('Reached %s: %s', trading_date, counts)
            trading_date = trading_date + datetime.timedelta(days=1)
        return counts

    def file_path(self, trading_date: datetime.date) -> pathlib.Path:
        """Gives the local path a day's zip file is saved at.

        Args:
            trading_date: The datetime.date of the trading day.

        Returns:
            The pathlib.Path of the zip file, under a folder named after the year.

        Raises:
            Nothing.
        """
        file_name = f'{trading_date.isoformat()}.csv.zip'
        return self.directory / str(trading_date.year) / file_name

    def url_for(self, trading_date: datetime.date) -> str:
        """Gives the archive address of a day's bhavcopy, in whichever format NSE used that day.

        Args:
            trading_date: The datetime.date of the trading day.

        Returns:
            The str URL of the zip file.

        Raises:
            Nothing.
        """
        if trading_date <= LAST_LEGACY_DATE:
            month = trading_date.strftime('%b').upper()
            return LEGACY_URL_TEMPLATE.format(
                year=trading_date.year,
                month=month,
                day=trading_date.strftime('%d'),
            )
        return UDIFF_URL_TEMPLATE.format(compact_date=trading_date.strftime('%Y%m%d'))

    def _download_one(self, trading_date: datetime.date) -> str:
        """Downloads one day's file and saves it.

        Args:
            trading_date: The datetime.date of the trading day.

        Returns:
            A str outcome: `downloaded`, `not_available` for a holiday or missing file, `refused` for HTTP 403 or 429, or `failed` for anything else.

        Raises:
            Nothing.
        """
        url = self.url_for(trading_date)
        try:
            response = self._session.get(url, timeout=60)
        except requests.RequestException as error:
            logging.warning('Request failed for %s (reason: %r)', trading_date, error)
            return 'failed'
        if response.status_code == 404:
            return 'not_available'
        if response.status_code in (403, 429):
            logging.warning('Archive refused %s with HTTP %s', trading_date, response.status_code)
            return 'refused'
        if response.status_code != 200 or not response.content.startswith(b'PK'):
            logging.warning('Unexpected answer for %s: HTTP %s', trading_date, response.status_code)
            return 'failed'
        target_path = self.file_path(trading_date)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = target_path.with_suffix('.partial')
        temporary_path.write_bytes(response.content)
        temporary_path.rename(target_path)
        return 'downloaded'

    def _read_not_available_dates(self) -> set[datetime.date]:
        """Reads the dates earlier runs found to have no file.

        Returns:
            A set of datetime.date values, empty when no earlier run recorded any.

        Raises:
            ValueError: The record file holds a line that is not an ISO date.
        """
        record_path = self.directory / NOT_AVAILABLE_FILE_NAME
        dates = set()
        if not record_path.exists():
            return dates
        for line in record_path.read_text().splitlines():
            if line.strip():
                dates.add(datetime.date.fromisoformat(line.strip()))
        return dates

    def _record_not_available(self, trading_date: datetime.date) -> None:
        """Appends a date with no file to the record, so later runs skip it.

        Args:
            trading_date: The datetime.date that had no file.

        Returns:
            None.

        Raises:
            OSError: The record file cannot be written.
        """
        record_path = self.directory / NOT_AVAILABLE_FILE_NAME
        with record_path.open('a') as record_file:
            record_file.write(f'{trading_date.isoformat()}\n')
