import numpy as np

from collections import defaultdict, namedtuple

from xzero import ZeroBase
from xzero.asset import Asset

from xone import logs

LongShort = namedtuple('LongShort', ['long', 'short'])


class SubPortfolio(ZeroBase):
    """
    Sub-Portfolio to hold long / short pairs or a group of assets
    """
    def __init__(self, port_name):

        super().__init__()
        self.portfolio_name = port_name
        self._positions_ = defaultdict(Asset)

    @property
    def _market_value_(self):
        """
        Long and short exposures
        """
        long, short = 0., 0.
        for asset in self._positions_.values():
            if asset.quantity > 0: long += asset.market_value
            elif asset.quantity < 0: short += asset.market_value
        return LongShort(long=long, short=short)

    @property
    def _quantity_(self):
        long, short = 0., 0.
        for asset in self._positions_.values():
            if asset.quantity > 0: long += asset.quantity
            elif asset.quantity < 0: short += asset.quantity
        return LongShort(long=long, short=short)

    @property
    def exposure(self):
        """
        Absolute value of one-sided expsoure
        """
        mkt_val = self._market_value_
        return max(mkt_val.long, abs(mkt_val.short))

    @property
    def side(self):
        """
        Side of the sub-portfolio
        Determined by the side of the first asset - NOT the net delta exposure
        """
        if len(self._positions_) == 0: return 0
        return int(np.sign(list(self._positions_.values())[0].quantity))

    @property
    def delta(self):
        """
        Delta between positive and negative positions

        Returns:
            Delta market values
        """
        mkt_val = self._market_value_
        return mkt_val.long + mkt_val.short

    @property
    def margin(self):
        """
        Assuming charged as max(long, short)
        """
        long, short = 0., 0.
        for asset in self._positions_.values():
            if asset.quantity == 0: continue
            if asset.quantity != 0 and asset.margin_req == 0:
                raise ValueError(f'Margin requirment for {asset.ticker} is 0.')
            if asset.quantity > 0: long += asset.market_value * asset.margin_req
            elif asset.quantity < 0: short += asset.market_value * asset.margin_req
        return max(long, abs(short))

    @property
    def is_flat(self):
        """
        Whether the sub-portfolio is flattened
        """
        qty = self._quantity_
        return qty.long == 0 and qty.short == 0


class Portfolio(ZeroBase):
    """
    Portfolio tracking cash
    """
    def __init__(self, init_cash):

        super().__init__()
        self.init_cash = init_cash

        # Internal values to track positions and performance
        self._cash_ = init_cash
        self._market_value_ = 0.
        self._margin_ = 0.
        self._positions_ = defaultdict(Asset)
        self._sub_port_ = defaultdict(SubPortfolio)
        self._performance_ = []

        self._logger_ = logs.get_logger(name_or_func='Porfrolio', types='stream')

    def market_value(self, snapshot):
        """
        Latest market value of all current holdings
        Removes sub-portfolio that is already flattened

        Args:
            snapshot: Market snapshot
        """
        mkt_val = 0.
        for asset in self._positions_.values():
            price = snapshot.price
            if not np.isnan(price): asset.price = snapshot.price
            mkt_val += asset.market_value

        flat = [port for port, sub in self._sub_port_.items() if sub.is_flat]
        for port in flat: self._sub_port_.pop(port)

        return mkt_val

    @property
    def margin(self):
        """
        Latest margin for all sub-portfolio
        """
        return np.array([port.margin for port in self._sub_port_.values()]).sum()
