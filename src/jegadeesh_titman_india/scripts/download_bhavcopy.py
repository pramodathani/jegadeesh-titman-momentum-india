"""Downloads NSE cash-market bhavcopy files for the momentum study.

Run from the repository root:

  python -m jegadeesh_titman_india.scripts.download_bhavcopy --start 1995-01-01 --end 2026-10-06
"""

import argparse
import datetime
import logging
import pathlib

from jegadeesh_titman_india.bhavcopy import bhavcopy_downloader


STUDY_DIRECTORY = pathlib.Path(__file__).resolve().parents[3]

RAW_DIRECTORY = STUDY_DIRECTORY / 'data' / 'bhavcopy' / 'raw'


class DownloadBhavcopyApplication:
    """The command-line program that downloads a range of bhavcopy files."""

    def run(self) -> None:
        """Reads the command line, downloads the files and logs the counts.

        Returns:
            None.

        Raises:
            BlockedByArchiveError: NSE's archive started refusing requests.
        """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        parser = argparse.ArgumentParser(description='Download NSE bhavcopy files.')
        parser.add_argument('--start', type=datetime.date.fromisoformat, default=datetime.date(1995, 1, 1))
        parser.add_argument('--end', type=datetime.date.fromisoformat, default=datetime.date.today())
        parser.add_argument('--pause', type=float, default=0.4)
        arguments = parser.parse_args()
        downloader = bhavcopy_downloader.BhavcopyDownloader(
            directory=RAW_DIRECTORY,
            start_date=arguments.start,
            end_date=arguments.end,
            pause_seconds=arguments.pause,
        )
        counts = downloader.download_all()
        logging.info('Finished: %s', counts)


if __name__ == '__main__':
    DownloadBhavcopyApplication().run()
