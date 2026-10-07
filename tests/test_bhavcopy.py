"""Tests of the bhavcopy corporate action handling, using the real Infosys bonus and IRCTC split as cases.

Run from the repository root:

  python -m pytest
"""

import json

import pandas as pd
import pytest

from jegadeesh_titman_india.bhavcopy import corporate_action_parser
from jegadeesh_titman_india.momentum.price_sources import bhavcopy_price_source


class TestCorporateActionParser:
    """Tests of CorporateActionParser on descriptions as NSE writes them."""

    @pytest.mark.parametrize(
        'subject, price_factor, dividend',
        [
            ('Bonus 1:1', 2.0, 0.0),
            ('Bonus-1:1', 2.0, 0.0),
            ('Bonus 1:2', 1.5, 0.0),
            ('Fv Split Rs.10/- To Rs.2/', 5.0, 0.0),
            ('Face Value Split (Sub-Division) - From Rs 10/- Per Share To Re 1/- Per Share', 10.0, 0.0),
            ('Bonus 1:1 And Face Value Split Rs.10/- To Rs.5/- Per Share', 4.0, 0.0),
            ('Consolidation Of Equity Shares From Re 1 Per Share To Rs 10 Per Share', 0.1, 0.0),
            ('Annual General Meeting/Dividend Rs. - 2.80/- Per Share', 1.0, 2.8),
            ('Interim Dividend - Rs 2 Per Share And Special Dividend - Rs 3 Per Share', 1.0, 5.0),
            ('Agm/Final Dividend-250%', 1.0, 25.0),
            ('Interim Dividend - Rs 3 Per Share / Rights 1:16 @ Premium Rs 400 Per Share', 1.0, 3.0),
        ],
    )
    def test_descriptions_give_factor_and_dividend(self, subject: str, price_factor: float, dividend: float):
        """Checks one description's price factor and dividend.

        Args:
            subject: The str description as NSE writes it.
            price_factor: The float expected price factor.
            dividend: The float expected dividend per share in rupees, for a face value of Rs 10.

        Returns:
            None.

        Raises:
            AssertionError: The parsed values are wrong.
        """
        action = {
            'symbol': 'TEST',
            'exDate': '04-Sep-2018',
            'faceVal': '10',
            'subject': subject,
        }
        parsed = corporate_action_parser.CorporateActionParser().parse_action(action)
        assert parsed['price_factor'] == pytest.approx(price_factor)
        assert parsed['dividend'] == pytest.approx(dividend)

    def test_nil_dividend_is_not_an_action(self):
        """Checks that a meeting with no dividend gives no row.

        Returns:
            None.

        Raises:
            AssertionError: A row was returned.
        """
        action = {
            'symbol': 'TEST',
            'exDate': '04-Sep-2018',
            'faceVal': '10',
            'subject': 'Agm/Dividend - Nil',
        }
        assert corporate_action_parser.CorporateActionParser().parse_action(action) is None


class TestBhavcopyPriceSource:
    """Tests of BhavcopyPriceSource adjustments, using real bhavcopy closes."""

    def test_bonus_and_split_days_have_ordinary_returns(self, tmp_path):
        """Checks that the Infosys 1:1 bonus and the IRCTC 1:5 split no longer look like crashes, where the Infosys action is given a Saturday ex-date so it must move to the next trading day.

        Args:
            tmp_path: The pathlib.Path of a temporary directory, given by pytest.

        Returns:
            None.

        Raises:
            AssertionError: A return is wrong.
        """
        store_directory = tmp_path / 'store'
        actions_directory = tmp_path / 'actions'
        store_directory.mkdir()
        actions_directory.mkdir()
        rows = pd.DataFrame(
            {
                'date': pd.to_datetime(
                    [
                        '2018-09-04',
                        '2021-10-27',
                        '2021-10-28',
                    ]
                ),
                'symbol': [
                    'INFY',
                    'IRCTC',
                    'IRCTC',
                ],
                'series': [
                    'EQ',
                    'EQ',
                    'EQ',
                ],
                'close': [
                    737.15,
                    4130.15,
                    913.50,
                ],
                'previous_close': [
                    1434.25,
                    4189.50,
                    4130.15,
                ],
                'traded_value': [
                    1.0,
                    1.0,
                    1.0,
                ],
                'isin': [
                    None,
                    None,
                    None,
                ],
            }
        )
        rows.to_parquet(store_directory / '2018.parquet', index=False)
        actions = [
            {
                'symbol': 'INFY',
                'exDate': '01-Sep-2018',
                'faceVal': '5',
                'subject': 'Bonus 1:1',
            },
            {
                'symbol': 'IRCTC',
                'exDate': '28-Oct-2021',
                'faceVal': '10',
                'subject': 'Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share',
            },
        ]
        (actions_directory / '2018.json').write_text(json.dumps(actions))
        source = bhavcopy_price_source.BhavcopyPriceSource(store_directory, actions_directory)
        panel = source.daily_panel().set_index(
            [
                'symbol',
                'date',
            ]
        )
        assert panel.loc[('INFY', pd.Timestamp('2018-09-04')), 'daily_return'] == pytest.approx(737.15 * 2 / 1434.25 - 1)
        assert panel.loc[('IRCTC', pd.Timestamp('2021-10-27')), 'daily_return'] == pytest.approx(4130.15 / 4189.50 - 1)
        assert panel.loc[('IRCTC', pd.Timestamp('2021-10-28')), 'daily_return'] == pytest.approx(913.50 * 5 / 4130.15 - 1)
