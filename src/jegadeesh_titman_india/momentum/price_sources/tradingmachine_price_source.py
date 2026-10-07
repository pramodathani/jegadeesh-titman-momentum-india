"""Daily NSE share and index prices from tradingmachine's Unified Broker Interface, cached locally.

UBI's adjusted prices account for splits and bonuses but not dividends, start around December 2019, and only cover shares listed today. The prices are fetched once with `fetch_and_cache` and then read from Parquet files, so the study does not call UBI on every run.

Typical usage example:

  source = TradingmachinePriceSource(cache_directory=pathlib.Path('data/tradingmachine'))
  source.fetch_and_cache()
  daily_panel = source.daily_panel()
"""

import logging
import pathlib

import pandas as pd

from tradingmachine.assets import instruments


MASTER_PATH = '/api/instruments/master'

PRICES_PATH = '/api/instruments/prices'

INDIA_TIME_ZONE = 'Asia/Kolkata'

FIRST_DATE = '2000-01-01'

BATCH_SIZE = 200

EXCLUDED_SYMBOL_FRAGMENTS = [
    'NSETEST',
]

INDEX_SYMBOLS = [
    'NIFTY',
    'NIFTY 500',
    'Nifty500 EW',
]

SHARES_FILE_NAME = 'daily_share_prices.parquet'

INDICES_FILE_NAME = 'daily_index_prices.parquet'


class TradingmachinePriceSource:
    """Daily adjusted closes and traded values for every current NSE share and three NSE indices.

    Attributes:
        cache_directory: The pathlib.Path holding the cached Parquet files.
        last_date: The str last date, as `YYYY-MM-DD`, to fetch prices up to.
    """

    def __init__(self, cache_directory: pathlib.Path, last_date: str = '2026-09-30'):
        """Initialises the source.

        Args:
            cache_directory: The pathlib.Path holding the cached Parquet files.
            last_date: The str last date, as `YYYY-MM-DD`, to fetch prices up to.

        Raises:
            Nothing.
        """
        self.cache_directory = cache_directory
        self.last_date = last_date

    def fetch_and_cache(self) -> None:
        """Fetches every NSE share's and the indices' daily prices from UBI and saves them as Parquet.

        Returns:
            None.

        Raises:
            UnifiedBrokerInterfaceError: UBI refused a request or could not be reached.
        """
        client = instruments.Instrument.shared_unified_broker_interface()
        share_rows = self._listed_shares(client, 'equities')
        logging.info('Fetching prices for %s shares', len(share_rows))
        share_prices = self._fetch_prices(client, share_rows)
        index_rows = []
        for row in self._listed_shares(client, 'equity_indices'):
            if row['symbol'] in INDEX_SYMBOLS:
                index_rows.append(row)
        index_prices = self._fetch_prices(client, index_rows)
        self.cache_directory.mkdir(parents=True, exist_ok=True)
        share_prices.to_parquet(self.cache_directory / SHARES_FILE_NAME, index=False)
        index_prices.to_parquet(self.cache_directory / INDICES_FILE_NAME, index=False)
        logging.info('Saved %s share rows and %s index rows', len(share_prices), len(index_prices))

    def daily_panel(self) -> pd.DataFrame:
        """Reads the cached share prices as one row per share per trading day.

        Returns:
            A pandas.DataFrame with `date`, `symbol`, `close`, `daily_return` and `traded_value` columns, sorted by symbol and date, where `daily_return` is the change in adjusted close since the share's previous trading day.

        Raises:
            FileNotFoundError: fetch_and_cache has not been run.
        """
        prices = pd.read_parquet(self.cache_directory / SHARES_FILE_NAME)
        prices = prices.sort_values(
            [
                'symbol',
                'date',
            ]
        ).reset_index(drop=True)
        prices['daily_return'] = prices.groupby('symbol')['close'].pct_change()
        prices['traded_value'] = prices['close'] * prices['volume']
        return prices[
            [
                'date',
                'symbol',
                'close',
                'daily_return',
                'traded_value',
            ]
        ]

    def index_closes(self) -> pd.DataFrame:
        """Reads the cached index closes as one column per index.

        Returns:
            A pandas.DataFrame indexed by date, with one column of closes per index symbol.

        Raises:
            FileNotFoundError: fetch_and_cache has not been run.
        """
        prices = pd.read_parquet(self.cache_directory / INDICES_FILE_NAME)
        return prices.pivot(index='date', columns='symbol', values='close').sort_index()

    def _listed_shares(self, client, segment: str) -> list[dict]:
        """Lists the NSE instruments in one segment, leaving out exchange test symbols.

        Args:
            client: The tradingmachine.unified_broker_interface.client.UnifiedBrokerInterface to ask.
            segment: The str UBI segment, `equities` or `equity_indices`.

        Returns:
            A list of dicts, each with at least `instrument_id` and `symbol`.

        Raises:
            UnifiedBrokerInterfaceError: UBI refused the request or could not be reached.
        """
        rows = client.get(
            MASTER_PATH,
            params={
                'exchange': 'nse',
                'segment': segment,
            },
        )
        kept_rows = []
        for row in rows:
            excluded = False
            for fragment in EXCLUDED_SYMBOL_FRAGMENTS:
                if fragment in row['symbol']:
                    excluded = True
            if not excluded:
                kept_rows.append(row)
        return kept_rows

    def _fetch_prices(self, client, rows: list[dict]) -> pd.DataFrame:
        """Fetches adjusted daily candles for the given instruments in batches.

        Args:
            client: The tradingmachine.unified_broker_interface.client.UnifiedBrokerInterface to ask.
            rows: A list of dicts, each with `instrument_id` and `symbol`.

        Returns:
            A pandas.DataFrame with `date`, `symbol`, `close` and `volume` columns, where `date` is the trading day without a time zone.

        Raises:
            UnifiedBrokerInterfaceError: UBI refused a whole batch or could not be reached.
        """
        frames = []
        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start:start + BATCH_SIZE]
            named_instruments = []
            for row in batch:
                named_instruments.append(
                    {
                        'instrument_id': row['instrument_id'],
                    }
                )
            body = {
                'instruments': named_instruments,
                'interval': 'day',
                'from': FIRST_DATE,
                'to': self.last_date,
                'adjusted': 'true',
            }
            response = client.post(PRICES_PATH, body=body)
            for result in response['results']:
                row = batch[result['request_index']]
                if result['status'] != 200:
                    logging.warning('No prices for %s: %s', row['symbol'], result.get('error'))
                    continue
                data = result['data']
                if not data['candles']:
                    continue
                frame = pd.DataFrame(data['candles'], columns=data['columns'])
                frame['date'] = pd.to_datetime(frame['time']).dt.tz_convert(INDIA_TIME_ZONE).dt.tz_localize(None).dt.normalize()
                frame['symbol'] = row['symbol']
                frames.append(
                    frame[
                        [
                            'date',
                            'symbol',
                            'close',
                            'volume',
                        ]
                    ]
                )
            logging.info('Fetched %s of %s', min(start + BATCH_SIZE, len(rows)), len(rows))
        return pd.concat(frames, ignore_index=True)
