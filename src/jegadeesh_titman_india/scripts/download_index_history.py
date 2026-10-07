"""Downloads NSE's daily index close files, from July 2012, for the study's benchmarks.

Run from the repository root after download_bhavcopy, whose dates are used as the trading days:

  python -m jegadeesh_titman_india.scripts.download_index_history
"""

import datetime
import logging
import pathlib

from jegadeesh_titman_india.bhavcopy import index_archive_downloader


STUDY_DIRECTORY = pathlib.Path(__file__).resolve().parents[3]

DATA_DIRECTORY = STUDY_DIRECTORY / 'data'

FIRST_DATE = datetime.date(2012, 7, 1)


class DownloadIndexHistoryApplication:
    """The command-line program that downloads NSE's daily index files."""

    def run(self) -> None:
        """Downloads the files and logs the counts.

        Returns:
            None.

        Raises:
            Nothing.
        """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        downloader = index_archive_downloader.IndexArchiveDownloader(
            index_directory=DATA_DIRECTORY / 'indices' / 'nse_daily',
            bhavcopy_raw_directory=DATA_DIRECTORY / 'bhavcopy' / 'raw',
            first_date=FIRST_DATE,
        )
        counts = downloader.download_all()
        logging.info('Finished: %s', counts)


if __name__ == '__main__':
    DownloadIndexHistoryApplication().run()
