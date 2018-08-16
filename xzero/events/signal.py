import pandas as pd
import numpy as np

from collections import namedtuple

from xzero.asset import Asset
from xzero.events import Event, EventType
from xzero.events.order import MarketOrderEvent, LimitOrderEvent

from xone import logs

TargetQuantity = namedtuple('TargetQuantity', ['asset', 'quantity'])


class SignalEvent(Event, event_type=EventType.SIGNAL):
    """
    Signal to generate order details
    """
    def __init__(
            self, timestamp, strategy: str, assets: list,
            order_type='MKT', target_value=None, weights=None, target_qty=None, **kwargs
    ):
        """
        Args:
            assets: list of assets
            order_type: order type, 'MKT' (default) or 'LMT'
            target_value: target notional
            weights: dict, weights of each asset
            target_qty: dict, target quantity for each asset
        """
        self._logger_ = logs.get_logger(SignalEvent, types='steram')
        assert (target_value is None) and (target_qty is None), ValueError(
            f'[{self.__class__.__name__}] Both target value and quantity are empty'
        )
        assert all(isinstance(asset, Asset) for asset in assets), ValueError(
            f'[{self.__class__.__name__}] Not all assets are of Asset class'
        )

        super().__init__()
        self.timestamp = pd.Timestamp(timestamp)
        self.strategy = strategy
        self.assets = assets
        self.order_type = order_type
        self.target_value = target_value
        self.weights = proper_weights(assets=assets, weights=weights)
        self.target_qty = target_qty
        self.info = kwargs
        self._order_type_ = LimitOrderEvent \
            if order_type.upper() == 'LMT' else MarketOrderEvent

    @property
    def order_quantity(self):
        """
        Order quantity for each asset
        """
        if isinstance(self.target_qty, dict):
            assert len(self.target_qty) == len(self.assets), ValueError(
                f'[{self.__class__.__name__}] Target quantities do not match # of assets'
            )
            qty = [
                TargetQuantity(asset=self.assets[n], quantity=quantity)
                for n, (ticker, quantity) in enumerate(self.target_qty.items())
            ]

        else:
            qty = [
                TargetQuantity(asset=asset, quantity=int(
                    self.target_value * self.weights[asset.ticker]
                    / asset.price / asset.lot_size
                )) for asset in self.assets
            ]

        return [t_qty for ticker, t_qty in qty if t_qty.quantity != 0]


def proper_weights(assets, weights=None):
    """
    Normalize weights to be capped by 1 and keep long / short ratio

    Args:
        assets: list of assets
        weights: dict of initial weights

    Returns:
        dict: weight of each asset

    Examples:
        >>> from xzero.asset import Equity
        >>>
        >>> a1 = Equity(ticker='AAPL', price=200., lot_size=100)
        >>> a2 = Equity(ticker='GOOG', price=1230, lot_size=100)
        >>> a3 = Equity(ticker='FB', price=180, lot_size=100)
        >>>
        >>> w1 = dict(AAPL=200, GOOG=200, FB=-300)
        >>> w2 = dict(AAPL=200, GOOG=-200)
        >>>
        >>> assert proper_weights([a1, a2, a3], w1) == dict(AAPL=.5, GOOG=.5, FB=-.75)
        >>> assert proper_weights([a1, a2, a3], w2) == dict(AAPL=1., GOOG=-1.)
    """
    if weights is None:
        if len(assets) == 2: weights = {assets[0].ticker: 1., assets[1]: -1.}
        elif len(assets) == 1: weights = {assets[0].ticker: 1.}

    else:
        # Normalized weights
        w_val = np.array([w for w in weights.values()])
        pos = w_val[w_val > 0].sum()
        neg = w_val[w_val < 0].sum()
        pos_to_neg = (pos / abs(neg)) if neg < 0 < pos else 1.

        for ticker, weight in weights.items():
            if weight == 0: continue
            weights[ticker] = weight / (pos if weight > 0 else (abs(neg) * pos_to_neg))

    return weights


if __name__ == '__main__':
    """
    CommandLine:
        python -m xzero.events.signal all
    """
    import xdoctest
    xdoctest.doctest_module(__file__)
