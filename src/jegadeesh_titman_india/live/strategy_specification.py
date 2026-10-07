"""Names one of the paper's strategy combinations, adapted to be held long-only in the Indian cash market.

The paper describes 32 combinations: ranking periods J of 3, 6, 9 and 12 months, holding periods K of 3, 6, 9 and 12 months, and either no gap or a one-week gap between ranking and holding. Each can be run on all NSE shares or on the 500 most traded, which gives 64 specifications. Only the winners decile is held, because shares cannot be shorted overnight in the cash market.

Typical usage example:

  specification = StrategySpecification(6, 6, 0, 'most_traded_500')
  print(specification.name, specification.tag)
  every_specification = StrategySpecification.all_specifications()
"""

UNIVERSE_SHORT_NAMES = {
    'most_traded_500': 'top500',
    'all_shares': 'all',
}

UNIVERSE_TAG_LETTERS = {
    'most_traded_500': 'T',
    'all_shares': 'A',
}

RANKING_MONTHS = [
    3,
    6,
    9,
    12,
]

HOLDING_MONTHS = [
    3,
    6,
    9,
    12,
]

SKIPPED_DAYS = [
    0,
    5,
]

NAME_PREFIX = 'jt-momentum'


class StrategySpecification:
    """One J-month/K-month long-only winners strategy on one universe of shares.

    Attributes:
        ranking_months: The int number of months, J in the paper, over which past returns are ranked.
        holding_months: The int number of months, K in the paper, each cohort is held.
        skipped_days: The int number of trading days between ranking and holding, 0 or 5.
        universe_name: The str universe, `most_traded_500` or `all_shares`.
    """

    def __init__(self, ranking_months: int, holding_months: int, skipped_days: int, universe_name: str):
        """Initialises the specification.

        Args:
            ranking_months: The int number of months over which past returns are ranked.
            holding_months: The int number of months each cohort is held.
            skipped_days: The int number of trading days between ranking and holding.
            universe_name: The str universe, `most_traded_500` or `all_shares`.

        Raises:
            ValueError: A value is not one the paper uses or the universe is unknown.
        """
        if ranking_months not in RANKING_MONTHS or holding_months not in HOLDING_MONTHS:
            raise ValueError(f'Not one of the paper\'s periods: {ranking_months=} {holding_months=}')
        if skipped_days not in SKIPPED_DAYS:
            raise ValueError(f'Not one of the paper\'s gaps: {skipped_days=}')
        if universe_name not in UNIVERSE_SHORT_NAMES:
            raise ValueError(f'Unknown universe: {universe_name=}')
        self.ranking_months = ranking_months
        self.holding_months = holding_months
        self.skipped_days = skipped_days
        self.universe_name = universe_name

    @classmethod
    def all_specifications(cls) -> list['StrategySpecification']:
        """Lists all 64 specifications: every combination the paper describes, on both universes.

        Returns:
            A list of StrategySpecification, the most-traded universe first.

        Raises:
            Nothing.
        """
        specifications = []
        for universe_name in UNIVERSE_SHORT_NAMES:
            for skipped_days in SKIPPED_DAYS:
                for ranking_months in RANKING_MONTHS:
                    for holding_months in HOLDING_MONTHS:
                        specifications.append(cls(ranking_months, holding_months, skipped_days, universe_name))
        return specifications

    @classmethod
    def from_name(cls, name: str) -> 'StrategySpecification':
        """Finds the specification with a given name.

        Args:
            name: The str name, such as `jt-momentum-j6-k6-skip0-top500`.

        Returns:
            The matching StrategySpecification.

        Raises:
            ValueError: No specification has that name.
        """
        for specification in cls.all_specifications():
            if specification.name == name:
                return specification
        raise ValueError(f'No strategy is named {name!r}')

    @property
    def name(self) -> str:
        """The str name the strategy's baskets are stored under, such as `jt-momentum-j6-k6-skip0-top500`."""
        universe = UNIVERSE_SHORT_NAMES[self.universe_name]
        return f'{NAME_PREFIX}-j{self.ranking_months}-k{self.holding_months}-skip{self.skipped_days}-{universe}'

    @property
    def tag(self) -> str:
        """The str order tag, at most 10 characters so every broker accepts it, such as `JT6x6s0T`."""
        letter = UNIVERSE_TAG_LETTERS[self.universe_name]
        return f'JT{self.ranking_months}x{self.holding_months}s{self.skipped_days}{letter}'
