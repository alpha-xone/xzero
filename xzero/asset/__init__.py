import pandas as pd

from enum import Enum, auto
from xzero import ZeroBase


class AssetType(Enum):

    Equity = auto()
    Futures = auto()
    Bond = auto()


class Asset(ZeroBase):
    """
    Interface for assets
    """
    def __init__(self):

        super().__init__()
        self.ticker = None
        self.price = None
        self.quantity = None
        self.lot_size = None
        self.margin_req = None

    def __init_subclass__(cls, asset_type=None, **kwargs):

        cls.asset_type = asset_type
        super().__init_subclass__(cls, **kwargs)

    @property
    def market_value(self):

        lot_size = 1. if self.lot_size is None else self.lot_size
        return self.price * self.quantity * lot_size


class Equity(Asset, asset_type=AssetType.Equity):
    """
    Equities
    """
    def __init__(self, ticker, price, quantity, tick_size, **kwargs):

        super().__init__()
        self.ticker = ticker
        self.price = price
        self.quantity = quantity
        self.tick_size = tick_size
        self.margin_req = kwargs.pop('margin_req', .15)
        # Fundamental data, earning dates, splits, analysts changes etc.
        self.info = kwargs


class Futures(Asset, asset_type=AssetType.Futures):
    """
    Futures
    """
    def __init__(self, ticker, price, quantity, lot_size, expiry, tick_size=None, **kwargs):

        super().__init__()
        self.ticker = ticker
        self.price = price
        self.quantity = quantity
        self.lot_size = lot_size
        self.expiry = pd.Timestamp(expiry)
        self.tick_size = tick_size
        self.margin_req = kwargs.pop('margin_req', .15)
        # Contract chains and etc.
        self.info = kwargs


class Bond(Asset, asset_type=AssetType.Bond):
    """
    Bond
    """
    def __init__(self, ticker, price, quantity, expiry, isin=None, **kwargs):
        """
        Args:
            quantity: in terms of notional - to match interface of other asset classes
        """
        super().__init__()
        self.ticker = ticker
        self.price = price
        self.quantity = quantity
        self.isin = isin
        self.expiry = expiry
        self.margin_req = kwargs.pop('margin_req', .3)
        # Issuer information, key dates (call / put etc.)
        self.info = kwargs
