"""Formats a pandas DataFrame as a Markdown table without needing the tabulate package.

Typical usage example:

  text = MarkdownTable(frame, decimals=4).render()
"""

import numbers

import pandas as pd


class MarkdownTable:
    """A DataFrame laid out as a GitHub-flavoured Markdown table, index first.

    Attributes:
        frame: The pandas.DataFrame to lay out.
        decimals: The int number of decimal places for floats.
    """

    def __init__(self, frame: pd.DataFrame, decimals: int = 4):
        """Initialises the table.

        Args:
            frame: The pandas.DataFrame to lay out.
            decimals: The int number of decimal places for floats.

        Raises:
            Nothing.
        """
        self.frame = frame
        self.decimals = decimals

    def render(self) -> str:
        """Gives the table as Markdown text.

        Returns:
            The str Markdown table, with a header row naming the index and the columns.

        Raises:
            Nothing.
        """
        index_name = self.frame.index.name if self.frame.index.name is not None else ''
        header = [str(index_name)]
        for column in self.frame.columns:
            header.append(str(column))
        lines = [
            '| ' + ' | '.join(header) + ' |',
            '|' + '---|' * len(header),
        ]
        for row in self.frame.itertuples(index=True, name=None):
            cells = []
            for value in row:
                cells.append(self._cell(value))
            lines.append('| ' + ' | '.join(cells) + ' |')
        return '\n'.join(lines)

    def _cell(self, value: object) -> str:
        """Formats one value for a table cell.

        Args:
            value: The value to format, of any type.

        Returns:
            The str cell text: floats rounded to the table's decimals, an empty string for NaN, and anything else as str.

        Raises:
            Nothing.
        """
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, numbers.Integral):
            return str(value)
        if isinstance(value, numbers.Real):
            if pd.isna(value):
                return ''
            return f'{value:.{self.decimals}f}'
        if value is None:
            return ''
        return str(value)
