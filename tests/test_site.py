"""Tests of the web app's data snapshot and local server, on a small made-up market.

Run from the repository root:

  python -m pytest
"""

import json
import socket

import pandas as pd
import pytest

from jegadeesh_titman_india import site_server
from jegadeesh_titman_india.live import strategy_specification
from jegadeesh_titman_india.momentum import monthly_return_panel
from jegadeesh_titman_india.momentum import site_snapshot


class TestSiteSnapshot:
    """Tests of SiteSnapshot."""

    def _panel(self) -> monthly_return_panel.MonthlyReturnPanel:
        """Builds a panel of 30 shares over 20 months in which share number n drifts up by n basis points a day.

        Returns:
            The monthly_return_panel.MonthlyReturnPanel.

        Raises:
            Nothing.
        """
        dates = []
        for month in pd.period_range('2020-01', periods=20, freq='M'):
            dates.extend(pd.bdate_range(month.start_time, month.end_time)[:20])
        rows = []
        for share_number in range(30):
            for date in dates:
                rows.append(
                    {
                        'date': date,
                        'symbol': f'S{share_number:02d}',
                        'daily_return': share_number * 0.0001,
                        'traded_value': 1e7 * (share_number + 1),
                    }
                )
        return monthly_return_panel.MonthlyReturnPanel(pd.DataFrame(rows))

    def _comparison_frame(self, months: pd.PeriodIndex) -> pd.DataFrame:
        """Builds net, gross and turnover columns for every strategy, all constant.

        Args:
            months: The pandas.PeriodIndex of months.

        Returns:
            A pandas.DataFrame in the form PortfolioComparison.net_returns returns.

        Raises:
            Nothing.
        """
        columns = {}
        for specification in strategy_specification.StrategySpecification.all_specifications():
            columns[specification.name] = pd.Series(0.01, index=months)
            columns[specification.name + '__gross'] = pd.Series(0.011, index=months)
            columns[specification.name + '__turnover'] = pd.Series(0.2, index=months)
        return pd.DataFrame(columns)

    def _table_one(self) -> pd.DataFrame:
        """Builds a Table I frame with every strategy's spread set to 1 percent.

        Returns:
            A pandas.DataFrame in the form StrategyGrid.table_one returns.

        Raises:
            Nothing.
        """
        rows = []
        for skipped_days in strategy_specification.SKIPPED_DAYS:
            for ranking_months in strategy_specification.RANKING_MONTHS:
                for holding_months in strategy_specification.HOLDING_MONTHS:
                    rows.append(
                        {
                            'ranking_months': ranking_months,
                            'holding_months': holding_months,
                            'skipped_days': skipped_days,
                            'portfolio': 'buy_minus_sell',
                            'mean': 0.01,
                            't_statistic': 2.0,
                            'first_month': '2021-01',
                            'last_month': '2021-08',
                        }
                    )
        return pd.DataFrame(rows)

    def test_winners_are_the_top_decile_and_files_are_written(self, tmp_path):
        """Checks that the winners of each month are the three highest-drifting shares and that every file exists.

        Args:
            tmp_path: The pathlib.Path of a temporary directory, given by pytest.

        Returns:
            None.

        Raises:
            AssertionError: The snapshot is wrong.
        """
        panel = self._panel()
        frame = self._comparison_frame(panel.months)
        table = pd.DataFrame(
            {
                'excess_annual': [
                    0.05,
                ],
                'first_month': [
                    '2021-01',
                ],
            },
            index=[
                'jt-momentum-j9-k3-skip0-top500',
            ],
        )
        table_one = {
            'most_traded_500': self._table_one(),
            'all_shares': self._table_one(),
        }
        snapshot = site_snapshot.SiteSnapshot(panel, frame, table, pd.Series(0.005, index=panel.months), table_one)
        sizes = snapshot.write(tmp_path)
        assert len(sizes) == 19
        cohorts = json.loads((tmp_path / 'cohorts' / 'all_j3_skip0.json').read_text())
        meta = json.loads((tmp_path / 'meta.json').read_text())
        last_winners = set()
        for row in cohorts['members'][-1]:
            last_winners.add(meta['symbols'][row[0]])
        assert last_winners == {
            'S27',
            'S28',
            'S29',
        }
        assert meta['paper_table_one']['skip5']['12'][0] == [
            0.0149,
            4.28,
        ]
        returns = json.loads((tmp_path / 'returns.json').read_text())
        assert returns['strategies']['jt-momentum-j9-k3-skip0-top500']['net'][0] == pytest.approx(0.01)


class TestSiteServer:
    """Tests of SiteServerApplication."""

    def test_free_port_skips_a_busy_port(self):
        """Checks that a port already listening is skipped.

        Returns:
            None.

        Raises:
            AssertionError: The busy port was returned.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            busy_port = listener.getsockname()[1]
            chosen = site_server.SiteServerApplication().free_port(busy_port)
            assert chosen != busy_port

    def test_site_files_ship_with_the_package(self):
        """Checks that the page, its script and the data index are inside the package.

        Returns:
            None.

        Raises:
            AssertionError: A file is missing.
        """
        for name in [
            'index.html',
            'app.js',
            'style.css',
            'data/meta.json',
        ]:
            assert (site_server.SITE_DIRECTORY / name).exists()
        assert len(list((site_server.SITE_DIRECTORY / 'data' / 'cohorts').glob('*.json'))) == 16
