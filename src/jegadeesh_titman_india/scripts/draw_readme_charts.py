"""Draws the README's growth chart, in light and dark versions, from the bhavcopy portfolio comparison, over the same months as its table.

Run from the repository root after compare_portfolios:

  python -m jegadeesh_titman_india.scripts.draw_readme_charts

The charts are written to `results/charts/`.
"""

import logging
import pathlib

import pandas as pd

from jegadeesh_titman_india.momentum import benchmark_history
from jegadeesh_titman_india.momentum import growth_chart


STUDY_DIRECTORY = pathlib.Path(__file__).resolve().parents[3]

DATA_DIRECTORY = STUDY_DIRECTORY / 'data'

RESULTS_DIRECTORY = STUDY_DIRECTORY / 'results'

NET_RETURNS_FILE = RESULTS_DIRECTORY / 'portfolio_comparison' / 'bhavcopy_from_2005_monthly_net_returns.csv'

COMPARISON_FILE = RESULTS_DIRECTORY / 'portfolio_comparison' / 'bhavcopy_from_2005.csv'

SERIES = {
    'jt-momentum-j9-k3-skip0-top500': 'Best liquid: J9/K3',
    'jt-momentum-j12-k3-skip5-top500': 'Paper\'s best: J12/K3, 1-week gap',
}


class DrawReadmeChartsApplication:
    """The command-line program that draws the README charts."""

    def run(self) -> None:
        """Reads the net returns and the benchmark and writes the light and dark charts.

        Returns:
            None.

        Raises:
            FileNotFoundError: compare_portfolios has not been run, or the index history is missing.
        """
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
        net_returns = pd.read_csv(NET_RETURNS_FILE, index_col=0)
        net_returns.index = pd.PeriodIndex(net_returns.index, freq='M')
        benchmark = benchmark_history.BenchmarkHistory(DATA_DIRECTORY).monthly_returns(total_return=True)
        series_by_label = {}
        for column, label in SERIES.items():
            series_by_label[label] = net_returns[column]
        series_by_label['NIFTY 500 total return'] = benchmark
        comparison = pd.read_csv(COMPARISON_FILE, index_col=0)
        comparison_start = pd.Period(comparison['first_month'].iloc[0], freq='M')
        frame = pd.DataFrame(series_by_label).dropna()
        frame = frame[frame.index >= comparison_start]
        common = {}
        for label in frame.columns:
            common[label] = frame[label]
        first = frame.index.min()
        last = frame.index.max()
        chart = growth_chart.GrowthChart(
            common,
            title=f'Growth of Rs 1, {first.strftime("%b %Y")} to {last.strftime("%b %Y")}',
            subtitle='Long-only winners of the 500 most-traded NSE shares, after Indian trading costs; log scale',
        )
        output_directory = RESULTS_DIRECTORY / 'charts'
        output_directory.mkdir(parents=True, exist_ok=True)
        (output_directory / 'growth-light.svg').write_text(chart.render(dark=False))
        (output_directory / 'growth-dark.svg').write_text(chart.render(dark=True))
        logging.info('Wrote charts to %s', output_directory)


if __name__ == '__main__':
    DrawReadmeChartsApplication().run()
