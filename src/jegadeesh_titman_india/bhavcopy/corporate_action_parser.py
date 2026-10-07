"""Turns NSE's corporate action descriptions into price factors and dividends per share.

A price factor is the number of shares an investor holds after the action for each share held before it, so a 1:1 bonus has a factor of 2 and a split from Rs 10 to Rs 2 a factor of 5. A dividend is in rupees per share. Rights issues, demergers and capital reductions are not parsed, because their descriptions do not carry the terms needed.

Typical usage example:

  parser = CorporateActionParser()
  adjustments = parser.parse_directory(pathlib.Path('data/bhavcopy/corporate_actions'))
"""

import json
import pathlib
import re

import pandas as pd


NUMBER_PATTERN = r'(\d+(?:\.\d+)?)'

BONUS_PATTERN = re.compile(r'bonus\s*[-:]?\s*' + NUMBER_PATTERN + r'\s*:\s*' + NUMBER_PATTERN)

PER_SHARE_PATTERN = re.compile(NUMBER_PATTERN + r'\s*(?:/-)?\s*per\s*share')

PERCENT_PATTERN = re.compile(NUMBER_PATTERN + r'\s*%')

DEFAULT_FACE_VALUE = 10.0


class CorporateActionParser:
    """The reader of NSE corporate action descriptions."""

    def parse_directory(self, directory: pathlib.Path) -> pd.DataFrame:
        """Reads every yearly JSON file in a directory and parses the actions in them.

        Args:
            directory: The pathlib.Path holding the yearly JSON files.

        Returns:
            A pandas.DataFrame with `symbol`, `ex_date`, `price_factor`, `dividend` and `subject` columns, one row per action that changes the share count or pays a dividend, where an action listed twice with the same description is kept once but a bonus and a split on the same day are both kept; the text of a dividend description is read only up to any mention of a rights issue, whose premium is not a dividend.

        Raises:
            OSError: A file cannot be read.
            json.JSONDecodeError: A file is not valid JSON.
        """
        rows = []
        for file_path in sorted(directory.glob('*.json')):
            for action in json.loads(file_path.read_text()):
                parsed = self.parse_action(action)
                if parsed is not None:
                    rows.append(parsed)
        frame = pd.DataFrame(rows)
        frame['normalised_subject'] = frame['subject'].str.lower().str.split().str.join(' ')
        frame = frame.drop_duplicates(
            subset=[
                'symbol',
                'ex_date',
                'normalised_subject',
            ]
        )
        frame = frame.drop(columns=['normalised_subject'])
        return frame.reset_index(drop=True)

    def parse_action(self, action: dict) -> dict | None:
        """Parses one action as NSE's API gives it.

        Args:
            action: A dict with at least `symbol`, `exDate`, `faceVal` and `subject` keys.

        Returns:
            A dict with `symbol`, `ex_date` as a pandas.Timestamp, float `price_factor`, float `dividend` and `subject`, or None when the action neither changes the share count nor pays a dividend, or has no usable ex-date.

        Raises:
            Nothing.
        """
        subject = action.get('subject') or ''
        lowered = ' '.join(subject.lower().split())
        ex_date = pd.to_datetime(action.get('exDate'), format='%d-%b-%Y', errors='coerce')
        if pd.isna(ex_date):
            return None
        price_factor = self.bonus_factor(lowered) * self.split_factor(lowered) * self.consolidation_factor(lowered)
        dividend = self.dividend(lowered, self._face_value(action.get('faceVal')))
        if price_factor == 1.0 and dividend == 0.0:
            return None
        return {
            'symbol': action['symbol'].strip(),
            'ex_date': ex_date,
            'price_factor': price_factor,
            'dividend': dividend,
            'subject': subject.strip(),
        }

    def bonus_factor(self, lowered: str) -> float:
        """Gives the price factor of a bonus issue described as `Bonus a:b`, meaning a new shares for every b held.

        Args:
            lowered: The str description in lower case with single spaces.

        Returns:
            The float factor (a + b) / b, or 1.0 when there is no bonus.

        Raises:
            Nothing.
        """
        match = BONUS_PATTERN.search(lowered)
        if match is None:
            return 1.0
        new_shares = float(match.group(1))
        held_shares = float(match.group(2))
        if held_shares == 0:
            return 1.0
        return (new_shares + held_shares) / held_shares

    def split_factor(self, lowered: str) -> float:
        """Gives the price factor of a face value split, the old face value divided by the new one.

        Args:
            lowered: The str description in lower case with single spaces.

        Returns:
            The float factor, or 1.0 when there is no split or its face values cannot be read.

        Raises:
            Nothing.
        """
        position = lowered.find('split')
        if position < 0:
            position = lowered.find('sub-division')
        if position < 0:
            return 1.0
        return self._ratio_of_first_two_numbers(lowered[position:])

    def consolidation_factor(self, lowered: str) -> float:
        """Gives the price factor of a consolidation, the old face value divided by the new, larger one.

        Args:
            lowered: The str description in lower case with single spaces.

        Returns:
            The float factor, below 1, or 1.0 when there is no consolidation or it comes with a capital reduction.

        Raises:
            Nothing.
        """
        position = lowered.find('consolidation')
        if position < 0 or 'reduction' in lowered:
            return 1.0
        return self._ratio_of_first_two_numbers(lowered[position:])

    def dividend(self, lowered: str, face_value: float) -> float:
        """Gives the rupee dividend per share described, adding up several dividends paid together.

        Args:
            lowered: The str description in lower case with single spaces.
            face_value: The float face value of the share, used for dividends given as a percentage.

        Returns:
            The float dividend in rupees per share, 0.0 when there is none.

        Raises:
            Nothing.
        """
        position = lowered.find('dividend')
        if position < 0:
            return 0.0
        text = lowered[position:].split('right')[0]
        per_share_amounts = PER_SHARE_PATTERN.findall(text)
        if per_share_amounts:
            total = 0.0
            for amount in per_share_amounts:
                total += float(amount)
            return total
        percentages = PERCENT_PATTERN.findall(text)
        total_percent = 0.0
        for percent in percentages:
            total_percent += float(percent)
        return total_percent / 100.0 * face_value

    def _ratio_of_first_two_numbers(self, text: str) -> float:
        """Divides the first number in a text by the second.

        Args:
            text: The str to read numbers from.

        Returns:
            The float ratio, or 1.0 when there are fewer than two numbers or the second is zero.

        Raises:
            Nothing.
        """
        numbers = re.findall(NUMBER_PATTERN, text)
        if len(numbers) < 2 or float(numbers[1]) == 0:
            return 1.0
        return float(numbers[0]) / float(numbers[1])

    def _face_value(self, text: str | None) -> float:
        """Reads a face value, falling back to Rs 10 when it is missing.

        Args:
            text: The str face value as NSE gives it, or None.

        Returns:
            The float face value in rupees.

        Raises:
            Nothing.
        """
        try:
            return float(text)
        except (TypeError, ValueError):
            return DEFAULT_FACE_VALUE
