"""Sorts shares into ten equal-sized groups by their ranking-period return.

Decile 1 holds the lowest past returns, the paper's "losers", and decile 10 the highest, the "winners".

Typical usage example:

  ranker = DecileRanker()
  deciles = ranker.assign(ranking_returns, eligible)
"""

import numpy as np
import pandas as pd


DECILE_COUNT = 10


class DecileRanker:
    """The rule that turns ranking returns into decile numbers, 1 for losers up to 10 for winners."""

    def assign(self, ranking_returns: pd.DataFrame, eligible: pd.DataFrame) -> np.ndarray:
        """Assigns every eligible share with a ranking return to a decile, separately in each month.

        Ties are broken by column order, so each decile holds as near to a tenth of the shares as possible.

        Args:
            ranking_returns: A pandas.DataFrame of ranking returns, months by symbols.
            eligible: A pandas.DataFrame of bools with the same shape, True where a share may be ranked.

        Returns:
            A numpy.ndarray of ints, months by symbols, holding the decile from 1 to 10, or 0 where a share is not ranked; a month with fewer than ten rankable shares is all 0.

        Raises:
            ValueError: The two frames do not have the same shape.
        """
        if ranking_returns.shape != eligible.shape:
            raise ValueError(f'Shapes differ: {ranking_returns.shape=} {eligible.shape=}')
        rankable = ranking_returns.where(eligible.astype(bool))
        ranks = rankable.rank(axis=1, method='first')
        counts = rankable.notna().sum(axis=1)
        deciles = np.zeros(rankable.shape, dtype=int)
        rank_values = ranks.to_numpy()
        for month_position in range(len(rankable)):
            share_count = int(counts.iloc[month_position])
            if share_count < DECILE_COUNT:
                continue
            month_ranks = rank_values[month_position]
            ranked = ~np.isnan(month_ranks)
            decile = np.floor((month_ranks[ranked] - 1.0) * DECILE_COUNT / share_count).astype(int) + 1
            deciles[month_position, ranked] = decile
        return deciles
