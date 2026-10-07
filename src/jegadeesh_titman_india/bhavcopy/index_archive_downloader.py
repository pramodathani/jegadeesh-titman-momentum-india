"""Downloads NSE's daily index close files, which give every NSE index's close and dividend yield for one day.

NSE's archive holds these files from July 2012. Only days with a downloaded share bhavcopy are requested, so holidays are skipped without a request.

Typical usage example:

  downloader = IndexArchiveDownloader(index_directory, bhavcopy_raw_directory, first_date=datetime.date(2012, 7, 1))
  downloader.download_all()
"""

import datetime
import logging
import pathlib
import time

import requests


URL_TEMPLATE = 'https://nsearchives.nseindia.com/content/indices/ind_close_all_{day}.csv'

REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36',
    'Accept': '*/*',
    'Referer': 'https://www.nseindia.com/',
}


class IndexArchiveDownloader:
    """A resumable, throttled downloader of NSE's daily index close files.

    Attributes:
        index_directory: The pathlib.Path the daily CSV files are saved in.
        bhavcopy_raw_directory: The pathlib.Path of the downloaded share bhavcopies, whose dates are the trading days to fetch.
        first_date: The datetime.date of the first day to fetch.
        pause_seconds: The float number of seconds to wait after each request.
    """

    def __init__(
        self,
        index_directory: pathlib.Path,
        bhavcopy_raw_directory: pathlib.Path,
        first_date: datetime.date,
        pause_seconds: float = 0.4,
    ):
        """Initialises the downloader.

        Args:
            index_directory: The pathlib.Path the daily CSV files are saved in.
            bhavcopy_raw_directory: The pathlib.Path of the downloaded share bhavcopies.
            first_date: The datetime.date of the first day to fetch.
            pause_seconds: The float number of seconds to wait after each request.

        Raises:
            Nothing.
        """
        self.index_directory = index_directory
        self.bhavcopy_raw_directory = bhavcopy_raw_directory
        self.first_date = first_date
        self.pause_seconds = pause_seconds
        self._session = requests.Session()
        self._session.headers.update(REQUEST_HEADERS)

    def trading_days(self) -> list[datetime.date]:
        """Lists the trading days from first_date that have a share bhavcopy.

        Returns:
            A sorted list of datetime.date values.

        Raises:
            Nothing.
        """
        days = []
        for file_path in self.bhavcopy_raw_directory.glob('*/*.csv.zip'):
            day = datetime.date.fromisoformat(file_path.name.removesuffix('.csv.zip'))
            if day >= self.first_date:
                days.append(day)
        return sorted(days)

    def download_all(self) -> dict:
        """Downloads every trading day's file not already saved.

        Returns:
            A dict with int counts under `downloaded`, `already_saved` and `missing`.

        Raises:
            Nothing.
        """
        self.index_directory.mkdir(parents=True, exist_ok=True)
        counts = {
            'downloaded': 0,
            'already_saved': 0,
            'missing': 0,
        }
        for day in self.trading_days():
            target_path = self.index_directory / f'{day.isoformat()}.csv'
            if target_path.exists():
                counts['already_saved'] += 1
                continue
            url = URL_TEMPLATE.format(day=day.strftime('%d%m%Y'))
            try:
                response = self._session.get(url, timeout=60)
            except requests.RequestException as error:
                logging.warning('Request failed for %s (reason: %r)', day, error)
                counts['missing'] += 1
                continue
            if response.status_code != 200 or not response.content.startswith(b'Index Name'):
                counts['missing'] += 1
            else:
                target_path.write_bytes(response.content)
                counts['downloaded'] += 1
            time.sleep(self.pause_seconds)
            if day.month == 1 and day.day <= 3:
                logging.info('Reached %s: %s', day, counts)
        return counts
