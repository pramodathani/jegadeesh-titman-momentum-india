"""Refreshes NSE's corporate action list and turns the downloaded bhavcopy files into yearly Parquet files.

Run from the repository root after download_bhavcopy has finished:

  python -m jegadeesh_titman_india.scripts.build_bhavcopy_store
"""

import datetime
import logging
import pathlib

from jegadeesh_titman_india.bhavcopy import bhavcopy_store
from jegadeesh_titman_india.bhavcopy import corporate_actions_downloader


STUDY_DIRECTORY = pathlib.Path(__file__).resolve().parents[3]

BHAVCOPY_DIRECTORY = STUDY_DIRECTORY / 'data' / 'bhavcopy'

FIRST_YEAR = 1995


class BuildBhavcopyStoreApplication:
    """The command-line program that prepares the bhavcopy data for the study."""

    def run(self) -> None:
        """Downloads any missing corporate action years and builds the Parquet store.

        Returns:
            None.

        Raises:
            requests.HTTPError: NSE refused the corporate action request.
            OSError: A file cannot be read or written.
        """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        downloader = corporate_actions_downloader.CorporateActionsDownloader(
            directory=BHAVCOPY_DIRECTORY / 'corporate_actions',
            first_year=FIRST_YEAR,
            last_year=datetime.date.today().year,
        )
        downloader.download_all()
        store = bhavcopy_store.BhavcopyStore(
            raw_directory=BHAVCOPY_DIRECTORY / 'raw',
            store_directory=BHAVCOPY_DIRECTORY / 'store',
        )
        row_counts = store.build()
        logging.info('Stored years: %s', row_counts)


if __name__ == '__main__':
    BuildBhavcopyStoreApplication().run()
