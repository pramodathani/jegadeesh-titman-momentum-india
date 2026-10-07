"""Downloads NSE's list of share corporate actions, one JSON file per calendar year.

The list comes from the data API behind NSE's corporate actions web page and gives, for each action, the share's symbol, its ex-date, its face value and a description such as `Bonus 1:1` or `Dividend - Rs 2 Per Share`.

Typical usage example:

  downloader = CorporateActionsDownloader(directory, first_year=1995, last_year=2026)
  downloader.download_all()
"""

import json
import logging
import pathlib
import time

import requests


API_URL = 'https://www.nseindia.com/api/corporates-corporateActions'

REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.nseindia.com/companies-listing/corporate-filings-actions',
}


class CorporateActionsDownloader:
    """A downloader of NSE's corporate actions for a range of years.

    Attributes:
        directory: The pathlib.Path the yearly JSON files are saved in.
        first_year: The int first calendar year to download.
        last_year: The int last calendar year to download.
        pause_seconds: The float number of seconds to wait between requests.
    """

    def __init__(self, directory: pathlib.Path, first_year: int, last_year: int, pause_seconds: float = 2.0):
        """Initialises the downloader.

        Args:
            directory: The pathlib.Path the yearly JSON files are saved in.
            first_year: The int first calendar year to download.
            last_year: The int last calendar year to download.
            pause_seconds: The float number of seconds to wait between requests.

        Raises:
            ValueError: first_year is after last_year.
        """
        if first_year > last_year:
            raise ValueError(f'first_year is after last_year: {first_year=} {last_year=}')
        self.directory = directory
        self.first_year = first_year
        self.last_year = last_year
        self.pause_seconds = pause_seconds
        self._session = requests.Session()
        self._session.headers.update(REQUEST_HEADERS)

    def download_all(self, refresh_last_year: bool = True) -> dict:
        """Downloads every year not already saved, and the last year again when asked.

        Args:
            refresh_last_year: A bool that is True to download the last year even if it is saved, because it may have grown.

        Returns:
            A dict mapping each int year downloaded to the int number of actions in it.

        Raises:
            requests.HTTPError: NSE answered a request with an error status.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        counts = {}
        for year in range(self.first_year, self.last_year + 1):
            file_path = self.directory / f'{year}.json'
            if file_path.exists() and not (refresh_last_year and year == self.last_year):
                continue
            parameters = {
                'index': 'equities',
                'from_date': f'01-01-{year}',
                'to_date': f'31-12-{year}',
            }
            response = self._session.get(API_URL, params=parameters, timeout=120)
            response.raise_for_status()
            actions = response.json()
            file_path.write_text(json.dumps(actions))
            counts[year] = len(actions)
            logging.info('Saved %s corporate actions for %s', len(actions), year)
            time.sleep(self.pause_seconds)
        return counts
