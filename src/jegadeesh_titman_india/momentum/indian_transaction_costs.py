"""The cost of buying and selling NSE shares for delivery, as a fraction of the value traded.

The statutory charges are those in force in 2026 for delivery trades through a discount broker that charges no brokerage on delivery. The market impact cost is an assumption, not a measurement, and is given separately so that it can be varied.

Typical usage example:

  costs = IndianTransactionCosts(impact_cost=0.001)
  net_returns = costs.net_returns(gross_returns, bought, sold)
"""

import pandas as pd


SECURITIES_TRANSACTION_TAX = 0.001

STAMP_DUTY_ON_BUYS = 0.00015

EXCHANGE_TRANSACTION_CHARGE = 0.0000297

SEBI_TURNOVER_FEE = 0.000001

GOODS_AND_SERVICES_TAX = 0.18


class IndianTransactionCosts:
    """The per-side cost rates of an NSE delivery trade, including an assumed market impact.

    Attributes:
        impact_cost: The float assumed market impact per side, as a fraction of the value traded.
        brokerage: The float brokerage per side, as a fraction of the value traded.
    """

    def __init__(self, impact_cost: float, brokerage: float = 0.0):
        """Initialises the cost rates.

        Args:
            impact_cost: The float assumed market impact per side, as a fraction of the value traded.
            brokerage: The float brokerage per side, as a fraction of the value traded.

        Raises:
            ValueError: A rate is negative.
        """
        if impact_cost < 0 or brokerage < 0:
            raise ValueError(f'Cost rates must not be negative: {impact_cost=} {brokerage=}')
        self.impact_cost = impact_cost
        self.brokerage = brokerage

    def buy_rate(self) -> float:
        """Gives the total cost of buying, as a fraction of the value bought.

        Returns:
            The float cost rate.

        Raises:
            Nothing.
        """
        return self._shared_rate() + STAMP_DUTY_ON_BUYS

    def sell_rate(self) -> float:
        """Gives the total cost of selling, as a fraction of the value sold.

        Returns:
            The float cost rate.

        Raises:
            Nothing.
        """
        return self._shared_rate()

    def net_returns(self, gross_returns: pd.Series, bought: pd.Series, sold: pd.Series) -> pd.Series:
        """Subtracts each month's trading costs from a portfolio's gross monthly returns.

        Args:
            gross_returns: A pandas.Series of monthly returns before costs.
            bought: A pandas.Series of the fraction of the portfolio bought at the start of each month.
            sold: A pandas.Series of the fraction of the portfolio sold at the start of each month.

        Returns:
            A pandas.Series of monthly returns after costs.

        Raises:
            Nothing.
        """
        monthly_cost = bought * self.buy_rate() + sold * self.sell_rate()
        return gross_returns - monthly_cost

    def _shared_rate(self) -> float:
        """Gives the part of the cost rate that applies to both buying and selling.

        Returns:
            The float cost rate: securities transaction tax, exchange and SEBI charges with GST on them and on brokerage, brokerage and market impact.

        Raises:
            Nothing.
        """
        fees = EXCHANGE_TRANSACTION_CHARGE + SEBI_TURNOVER_FEE + self.brokerage
        return SECURITIES_TRANSACTION_TAX + fees * (1.0 + GOODS_AND_SERVICES_TAX) + self.impact_cost
