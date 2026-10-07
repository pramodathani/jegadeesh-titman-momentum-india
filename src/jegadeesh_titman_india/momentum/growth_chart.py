"""Draws the growth of one rupee for a few monthly return series as a static SVG line chart, without a plotting library.

The chart has a logarithmic value axis, so equal vertical distances mean equal percentage changes, a legend, and a direct label at the end of each line. Light and dark versions are drawn from the same data so a README can show the one matching the reader's theme.

Typical usage example:

  chart = GrowthChart(series_by_label, title='Growth of Rs 1')
  pathlib.Path('growth-light.svg').write_text(chart.render(dark=False))
"""

import math

import pandas as pd


WIDTH = 760

HEIGHT = 380

LEFT = 56

RIGHT = 150

TOP = 56

BOTTOM = 40

LIGHT_COLOURS = {
    'surface': '#fcfcfb',
    'text_primary': '#0b0b0b',
    'text_secondary': '#52514e',
    'muted': '#898781',
    'gridline': '#e1e0d9',
    'baseline': '#c3c2b7',
    'series': [
        '#2a78d6',
        '#eb6834',
        '#1baf7a',
    ],
}

DARK_COLOURS = {
    'surface': '#1a1a19',
    'text_primary': '#ffffff',
    'text_secondary': '#c3c2b7',
    'muted': '#898781',
    'gridline': '#2c2c2a',
    'baseline': '#383835',
    'series': [
        '#3987e5',
        '#d95926',
        '#199e70',
    ],
}

LOG_TICKS = [
    0.25,
    0.5,
    1,
    2,
    5,
    10,
    20,
    50,
    100,
]


class GrowthChart:
    """A line chart of cumulative growth for up to three monthly return series.

    Attributes:
        series_by_label: A dict mapping each str legend label to a pandas.Series of monthly returns indexed by month, all over the same months.
        title: The str title drawn at the top of the chart.
        subtitle: The str smaller line drawn under the title.
    """

    def __init__(self, series_by_label: dict, title: str, subtitle: str = ''):
        """Initialises the chart.

        Args:
            series_by_label: A dict mapping each str label to a pandas.Series of monthly returns indexed by a monthly pandas.PeriodIndex.
            title: The str title.
            subtitle: The str smaller line under the title.

        Raises:
            ValueError: There are no series or more than three.
        """
        if not series_by_label or len(series_by_label) > 3:
            raise ValueError(f'Between one and three series are needed: {len(series_by_label)=}')
        self.series_by_label = series_by_label
        self.title = title
        self.subtitle = subtitle

    def render(self, dark: bool) -> str:
        """Draws the chart as SVG text.

        Args:
            dark: A bool that is True for the dark-mode colours.

        Returns:
            The str SVG document.

        Raises:
            Nothing.
        """
        colours = DARK_COLOURS if dark else LIGHT_COLOURS
        wealth_by_label = {}
        for label, returns in self.series_by_label.items():
            wealth = (1.0 + returns.fillna(0.0)).cumprod()
            start = pd.Series([1.0], index=[returns.index[0] - 1])
            wealth_by_label[label] = pd.concat(
                [
                    start,
                    wealth,
                ]
            )
        months = next(iter(wealth_by_label.values())).index
        lowest = min(float(wealth.min()) for wealth in wealth_by_label.values())
        highest = max(float(wealth.max()) for wealth in wealth_by_label.values())
        self._log_low = math.log(lowest * 0.9)
        self._log_high = math.log(highest * 1.1)
        self._month_count = len(months)
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{self._escape(self.title)}">',
            f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{colours["surface"]}"/>',
            f'<text x="{LEFT}" y="24" font-family="Roboto, Helvetica, Arial, sans-serif" font-size="15" font-weight="700" fill="{colours["text_primary"]}">{self._escape(self.title)}</text>',
            f'<text x="{LEFT}" y="42" font-family="Roboto, Helvetica, Arial, sans-serif" font-size="11" fill="{colours["text_secondary"]}">{self._escape(self.subtitle)}</text>',
        ]
        parts.extend(self._grid(colours, lowest, highest))
        parts.extend(self._year_axis(colours, months))
        parts.extend(self._lines(colours, wealth_by_label))
        parts.extend(self._legend(colours))
        parts.append('</svg>')
        return '\n'.join(parts) + '\n'

    def _x(self, position: int) -> float:
        """Gives the horizontal pixel of a month.

        Args:
            position: The int position of the month, 0 for the starting point.

        Returns:
            The float x coordinate.

        Raises:
            Nothing.
        """
        plot_width = WIDTH - LEFT - RIGHT
        return LEFT + plot_width * position / max(self._month_count - 1, 1)

    def _y(self, value: float) -> float:
        """Gives the vertical pixel of a wealth value on the logarithmic axis.

        Args:
            value: The float wealth, above zero.

        Returns:
            The float y coordinate.

        Raises:
            Nothing.
        """
        plot_height = HEIGHT - TOP - BOTTOM
        share = (math.log(value) - self._log_low) / (self._log_high - self._log_low)
        return TOP + plot_height * (1.0 - share)

    def _grid(self, colours: dict, lowest: float, highest: float) -> list[str]:
        """Draws the horizontal gridlines and their value labels.

        Args:
            colours: The dict of colours for the mode.
            lowest: The float smallest wealth drawn.
            highest: The float largest wealth drawn.

        Returns:
            A list of str SVG elements.

        Raises:
            Nothing.
        """
        parts = []
        for tick in LOG_TICKS:
            if tick < lowest * 0.9 or tick > highest * 1.1:
                continue
            y = self._y(tick)
            stroke = colours['baseline'] if tick == 1 else colours['gridline']
            parts.append(f'<line x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{y:.1f}" y2="{y:.1f}" stroke="{stroke}" stroke-width="1"/>')
            parts.append(f'<text x="{LEFT - 8}" y="{y + 4:.1f}" text-anchor="end" font-family="Roboto, Helvetica, Arial, sans-serif" font-size="11" fill="{colours["muted"]}">Rs {tick:g}</text>')
        return parts

    def _year_axis(self, colours: dict, months: pd.Index) -> list[str]:
        """Draws a year label under every second January.

        Args:
            colours: The dict of colours for the mode.
            months: The pandas.Index of months, starting with the month before the first return.

        Returns:
            A list of str SVG elements.

        Raises:
            Nothing.
        """
        parts = []
        for position, month in enumerate(months):
            if month.month == 1 and month.year % 2 == 0:
                x = self._x(position)
                parts.append(f'<text x="{x:.1f}" y="{HEIGHT - BOTTOM + 18}" text-anchor="middle" font-family="Roboto, Helvetica, Arial, sans-serif" font-size="11" fill="{colours["muted"]}">{month.year}</text>')
        return parts

    def _lines(self, colours: dict, wealth_by_label: dict) -> list[str]:
        """Draws each series as a 2-pixel line with its final value labelled at the right.

        Args:
            colours: The dict of colours for the mode.
            wealth_by_label: A dict mapping each str label to a pandas.Series of wealth.

        Returns:
            A list of str SVG elements.

        Raises:
            Nothing.
        """
        parts = []
        for number, (label, wealth) in enumerate(wealth_by_label.items()):
            points = []
            for position, value in enumerate(wealth.to_numpy()):
                points.append(f'{self._x(position):.1f},{self._y(float(value)):.1f}')
            colour = colours['series'][number]
            parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{colour}" stroke-width="2" stroke-linejoin="round"/>')
        label_positions = []
        for number, (label, wealth) in enumerate(wealth_by_label.items()):
            colour = colours['series'][number]
            final_value = float(wealth.iloc[-1])
            end_x = self._x(len(wealth) - 1)
            end_y = self._y(final_value)
            label_y = end_y
            for other_y in label_positions:
                if abs(label_y - other_y) < 16:
                    if label_y >= other_y:
                        label_y = other_y + 16
                    else:
                        label_y = other_y - 16
            label_positions.append(label_y)
            parts.append(f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="4" fill="{colour}" stroke="{colours["surface"]}" stroke-width="2"/>')
            parts.append(f'<line x1="{end_x + 10:.1f}" x2="{end_x + 20:.1f}" y1="{label_y:.1f}" y2="{label_y:.1f}" stroke="{colour}" stroke-width="3" stroke-linecap="round"/>')
            parts.append(f'<text x="{end_x + 26:.1f}" y="{label_y + 4:.1f}" font-family="Roboto, Helvetica, Arial, sans-serif" font-size="12" font-weight="700" fill="{colours["text_primary"]}">Rs {final_value:.1f}</text>')
        return parts

    def _legend(self, colours: dict) -> list[str]:
        """Draws a legend of short coloured lines and labels above the plot, right of the title.

        Args:
            colours: The dict of colours for the mode.

        Returns:
            A list of str SVG elements.

        Raises:
            Nothing.
        """
        parts = []
        y = TOP - 4
        x = LEFT
        for number, label in enumerate(self.series_by_label):
            colour = colours['series'][number]
            parts.append(f'<line x1="{x}" x2="{x + 18}" y1="{y}" y2="{y}" stroke="{colour}" stroke-width="2"/>')
            parts.append(f'<text x="{x + 24}" y="{y + 4}" font-family="Roboto, Helvetica, Arial, sans-serif" font-size="11" fill="{colours["text_secondary"]}">{self._escape(label)}</text>')
            x += 32 + 6 * len(label)
        return parts

    def _escape(self, text: str) -> str:
        """Escapes the characters SVG text cannot contain directly.

        Args:
            text: The str to escape.

        Returns:
            The str with &, < and > replaced by entities.

        Raises:
            Nothing.
        """
        return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
