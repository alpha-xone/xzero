import pandas as pd

from enum import Enum, auto

from xzero import ZeroBase
from xzero.execution import commission


class AssetType(Enum):

    Equity = auto()
    Futures = auto()
    Bond = auto()


class Financing(ZeroBase):
    """
    Financing costs
    """
    def __init__(self, borrow_cost=0., financing_cost=0.):

        super().__init__()
        self.borrow_cost = borrow_cost
        self.financing_cost = financing_cost


class Asset(ZeroBase):
    """
    Interface for assets
    """
    def __init__(self, **kwargs):

        super().__init__()
        self.ticker = None
        self.price = None
        self.quantity = None
        self.lot_size = None
        self.margin_req = None
        self.comms = commission.comms('dollar__2')

        # Borrow / financing / etc.
        self.financing = Financing(
            borrow_cost=kwargs.pop('borrow_cost', 0.),
            financing_cost=kwargs.pop('financing_cost', 0.)
        )

    def __init_subclass__(cls, asset_type=None, **kwargs):

        cls.asset_type = asset_type
        super().__init_subclass__(**kwargs)

    @property
    def market_value(self):

        lot_size = 1. if self.lot_size is None else self.lot_size
        return self.price * self.quantity * lot_size


class Equity(Asset, asset_type=AssetType.Equity):
    """
    Equities
    """
    def __init__(
            self, ticker, price, lot_size, quantity=0, comms='dollar__2',
            tick_size=.01, margin_req=.15, **kwargs
    ):

        super().__init__(**kwargs)
        self.ticker = ticker
        self.price = price
        self.lot_size = lot_size
        self.quantity = quantity
        self.tick_size = tick_size
        self.comms = commission.comms(comms)
        self.margin_req = margin_req
        # Fundamental data, earning dates, splits, analysts changes etc.
        self.info = kwargs


class Futures(Asset, asset_type=AssetType.Futures):
    """
    Futures
    """
    def __init__(
            self, ticker, price, lot_size, expiry, quantity=0,
            comms='dollar__1', tick_size=None, margin_req=.15, **kwargs
    ):

        super().__init__(**kwargs)
        self.ticker = ticker
        self.price = price
        self.quantity = quantity
        self.lot_size = lot_size
        self.expiry = pd.Timestamp(expiry)
        self.tick_size = tick_size
        self.comms = commission.comms(comms)
        self.margin_req = margin_req
        # Contract chains and etc.
        self.info = kwargs


class Bond(Asset, asset_type=AssetType.Bond):
    """
    Bond
    """
    def __init__(
            self, ticker, price, expiry, quantity=0,
            comms='dollar__5', isin=None, margin_req=.3, **kwargs
    ):
        """
        Args:
            quantity: in terms of notional - to match interface of other asset classes
        """
        super().__init__(**kwargs)
        self.ticker = ticker
        self.price = price
        self.quantity = quantity
        self.isin = isin
        self.expiry = expiry
        self.comms = commission.comms(comms)
        self.margin_req = margin_req
        # Issuer information, key dates (call / put etc.)
        self.info = kwargs
