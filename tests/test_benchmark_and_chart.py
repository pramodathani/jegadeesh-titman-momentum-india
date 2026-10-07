"""Tests of the benchmark history and the growth chart, on small made-up files.

Run from the repository root:

  python -m pytest
"""

import pandas as pd
import pytest

from jegadeesh_titman_india.momentum import benchmark_history
from jegadeesh_titman_india.momentum import growth_chart


class TestBenchmarkHistory:
    """Tests of BenchmarkHistory."""

    def _write_nse_day(self, directory, day: str, name: str, close: float, dividend_yield: float) -> None:
        """Writes one NSE daily index file holding a single index row.

        Args:
            directory: The pathlib.Path of the NSE daily folder.
            day: The str date as `YYYY-MM-DD`.
            name: The str index name as NSE writes it.
            close: The float closing level.
            dividend_yield: The float dividend yield in percent.

        Returns:
            None.

        Raises:
            OSError: The file cannot be written.
        """
        frame = pd.DataFrame(
            [
                {
                    'Index Name': name,
                    'Index Date': day,
                    'Closing Index Value': close,
                    'Div Yield': dividend_yield,
                },
            ]
        )
        frame.to_csv(directory / f'{day}.csv', index=False)

    def test_nse_months_win_and_cache_fills_earlier_months(self, tmp_path):
        """Checks that NSE returns are used where they exist, the cache only before them, and old index names are recognised.

        Args:
            tmp_path: The pathlib.Path of a temporary directory, given by pytest.

        Returns:
            None.

        Raises:
            AssertionError: The spliced returns are wrong.
        """
        nse_directory = tmp_path / 'indices' / 'nse_daily'
        nse_directory.mkdir(parents=True)
        self._write_nse_day(nse_directory, '2012-07-31', 'S&P CNX 500', 100.0, 1.2)
        self._write_nse_day(nse_directory, '2012-08-31', 'CNX 500', 110.0, 1.2)
        self._write_nse_day(nse_directory, '2012-09-28', 'Nifty 500', 121.0, 1.2)
        cache_directory = tmp_path / 'tradingmachine'
        cache_directory.mkdir()
        cache = pd.DataFrame(
            {
                'date': pd.to_datetime(
                    [
                        '2012-05-31',
                        '2012-06-29',
                        '2012-07-31',
                        '2012-08-31',
                    ]
                ),
                'symbol': [
                    'NIFTY 500',
                    'NIFTY 500',
                    'NIFTY 500',
                    'NIFTY 500',
                ],
                'close': [
                    50.0,
                    60.0,
                    90.0,
                    999.0,
                ],
            }
        )
        cache.to_parquet(cache_directory / 'daily_index_prices.parquet', index=False)
        history = benchmark_history.BenchmarkHistory(tmp_path)
        price = history.monthly_returns(total_return=False)
        assert price[pd.Period('2012-06', 'M')] == pytest.approx(0.2)
        assert price[pd.Period('2012-07', 'M')] == pytest.approx(0.5)
        assert price[pd.Period('2012-08', 'M')] == pytest.approx(0.1)
        assert price[pd.Period('2012-09', 'M')] == pytest.approx(0.1)
        total = history.monthly_returns(total_return=True)
        assert total[pd.Period('2012-09', 'M')] == pytest.approx(0.1 + 0.012 / 12)
        assert total[pd.Period('2012-06', 'M')] == pytest.approx(0.2 + 0.012 / 12)

    def test_missing_data_raises(self, tmp_path):
        """Checks that a folder with neither source raises FileNotFoundError.

        Args:
            tmp_path: The pathlib.Path of a temporary directory, given by pytest.

        Returns:
            None.

        Raises:
            AssertionError: No error was raised.
        """
        with pytest.raises(FileNotFoundError):
            benchmark_history.BenchmarkHistory(tmp_path).monthly_returns(total_return=False)


class TestGrowthChart:
    """Tests of GrowthChart."""

    def test_end_labels_show_final_wealth_in_both_modes(self):
        """Checks that a series doubling over two months ends labelled Rs 2.0 and the dark version uses the dark surface.

        Returns:
            None.

        Raises:
            AssertionError: The SVG is wrong.
        """
        months = pd.period_range('2020-01', periods=2, freq='M')
        returns = pd.Series(
            [
                1.0,
                0.0,
            ],
            index=months,
        )
        series_by_label = {
            'Test': returns,
        }
        chart = growth_chart.GrowthChart(series_by_label, title='Test chart')
        light = chart.render(dark=False)
        dark = chart.render(dark=True)
        assert 'Rs 2.0</text>' in light
        assert '#fcfcfb' in light
        assert '#1a1a19' in dark

    def test_more_than_three_series_are_refused(self):
        """Checks that a fourth series is refused rather than given a fourth colour.

        Returns:
            None.

        Raises:
            AssertionError: No error was raised.
        """
        series = pd.Series([0.0], index=pd.period_range('2020-01', periods=1, freq='M'))
        four_series = {
            'A': series,
            'B': series,
            'C': series,
            'D': series,
        }
        with pytest.raises(ValueError):
            growth_chart.GrowthChart(four_series, title='Too many')
