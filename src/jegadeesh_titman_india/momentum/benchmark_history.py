"""Monthly NIFTY 500 returns for the benchmark, as price returns or approximate total returns.

Two sources are read when present, both as plain files:

- NSE's daily index close files in `data/indices/nse_daily/`, available from July 2012, which also give the index's dividend yield.
- The tradingmachine index cache `data/tradingmachine/daily_index_prices.parquet`, which reaches back to 2005 but is only available to someone running tradingmachine's Unified Broker Interface. Reading it needs only pandas.

Monthly returns from NSE's files are used wherever they exist, and the cache fills the months before. The approximate total return adds one twelfth of the month's average dividend yield to the price return; before July 2012, when no yield is available, the average yield of the later years is used.

Typical usage example:

  history = BenchmarkHistory(data_directory)
  total_returns = history.monthly_returns(total_return=True)
"""

import logging
import pathlib

import pandas as pd


INDEX_NAME = 'NIFTY 500'

NSE_NAMES = [
    'S&P CNX 500',
    'CNX 500',
    'Nifty 500',
    'NIFTY 500',
]


class BenchmarkHistory:
    """The NIFTY 500's monthly history, spliced from NSE's files and the tradingmachine cache.

    Attributes:
        data_directory: The pathlib.Path of the study's data folder.
    """

    def __init__(self, data_directory: pathlib.Path):
        """Initialises the history.

        Args:
            data_directory: The pathlib.Path of the study's data folder.

        Raises:
            Nothing.
        """
        self.data_directory = data_directory
        self._nse_daily = None

    def monthly_returns(self, total_return: bool) -> pd.Series:
        """Gives the NIFTY 500's monthly return.

        Args:
            total_return: A bool that is True to add the dividend yield to the price return.

        Returns:
            A pandas.Series of monthly returns indexed by month, named after the index.

        Raises:
            FileNotFoundError: Neither source has any data.
        """
        nse_returns = pd.Series(dtype=float)
        nse_daily = self._read_nse_daily()
        if len(nse_daily) > 0:
            nse_closes = nse_daily['close'].groupby(nse_daily.index.to_period('M')).last()
            nse_returns = nse_closes.pct_change().dropna()
        cache_returns = pd.Series(dtype=float)
        cache_path = self.data_directory / 'tradingmachine' / 'daily_index_prices.parquet'
        if cache_path.exists():
            cache = pd.read_parquet(cache_path)
            cache = cache[cache['symbol'] == INDEX_NAME].set_index('date').sort_index()
            cache_closes = cache['close'].groupby(cache.index.to_period('M')).last()
            cache_returns = cache_closes.pct_change().dropna()
        if len(nse_returns) == 0 and len(cache_returns) == 0:
            raise FileNotFoundError(f'No NIFTY 500 history in {self.data_directory}; run download_index_history')
        earlier = cache_returns[~cache_returns.index.isin(nse_returns.index)]
        if len(nse_returns) > 0:
            earlier = earlier[earlier.index < nse_returns.index.min()]
        returns = pd.concat(
            [
                earlier,
                nse_returns,
            ]
        ).sort_index()
        if total_return:
            returns = returns + self._monthly_dividend_yield(returns.index)
        logging.info('Benchmark months: %s from the tradingmachine cache, %s from NSE files', len(earlier), len(nse_returns))
        return returns.rename(INDEX_NAME)

    def _monthly_dividend_yield(self, months: pd.PeriodIndex) -> pd.Series:
        """Gives one twelfth of each month's average dividend yield, filling months without a yield with the overall average.

        Args:
            months: A pandas.PeriodIndex of the months wanted.

        Returns:
            A pandas.Series of monthly dividend returns indexed by months, 0 for every month when no yield is known at all.

        Raises:
            Nothing.
        """
        nse_daily = self._read_nse_daily()
        if len(nse_daily) == 0:
            return pd.Series(0.0, index=months)
        yields = nse_daily['dividend_yield'].groupby(nse_daily.index.to_period('M')).mean() / 100.0 / 12.0
        return yields.reindex(months).fillna(yields.mean())

    def _read_nse_daily(self) -> pd.DataFrame:
        """Reads the NIFTY 500 rows of every downloaded NSE daily index file, once.

        Returns:
            A pandas.DataFrame indexed by date with float `close` and `dividend_yield` columns, the yield in percent, empty when no file has been downloaded.

        Raises:
            KeyError: A file lacks one of the expected columns.
        """
        if self._nse_daily is not None:
            return self._nse_daily
        rows = []
        for file_path in sorted((self.data_directory / 'indices' / 'nse_daily').glob('*.csv')):
            day = pd.Timestamp(file_path.stem)
            frame = pd.read_csv(file_path)
            frame.columns = [column.strip() for column in frame.columns]
            names = frame['Index Name'].astype(str).str.strip()
            match = frame[names.isin(NSE_NAMES)]
            if len(match) == 0:
                continue
            row = match.iloc[0]
            rows.append(
                {
                    'date': day,
                    'close': float(row['Closing Index Value']),
                    'dividend_yield': pd.to_numeric(row['Div Yield'], errors='coerce'),
                }
            )
        if not rows:
            self._nse_daily = pd.DataFrame(
                columns=[
                    'close',
                    'dividend_yield',
                ]
            )
        else:
            self._nse_daily = pd.DataFrame(rows).set_index('date').sort_index()
        return self._nse_daily
