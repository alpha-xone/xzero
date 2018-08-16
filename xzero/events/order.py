import pandas as pd

from abc import ABCMeta

from xzero.asset import Asset
from xzero.events import Event, EventType


class ExecutionEvent(Event, event_type=EventType.EXECUTION):
    """
    Base class for Signal, Order and Fill events
    """
    __metaclass__ = ABCMeta

    def __init__(self, timestamp, strategy, asset: Asset, quantity, **kwargs):
        """
        Args:
            timestamp: timestamp of event
            strategy: order strategy - helps grouping pairs / sub-strategies together
            asset: traded asset
            quantity: quantity to trade or filled
            **kwargs: other infomation

        Examples:
            >>> from xzero.asset import Equity
            >>>
            >>> eqy = Equity(ticker='AAPL', price=200, lot_size=100)
            >>> info_dict = dict(
            >>>     timestamp='2018-07-05', strategy='Growth', asset=eqy, quantity=100
            >>> )
            >>> ex = ExecutionEvent.from_dict(**info_dict)
            >>> res = 'ExecutionEvent(timestamp=2018-07-05 00:00:00, strategy=Growth, '
            >>> res += 'asset=Equity(ticker=AAPL, price=200, quantity=0, lot_size=100, '
            >>> res += 'margin_req=0.15, comms=PerDollar(cost=0.0002, min_cost=0.0), '
            >>> res += 'financing=Financing(borrow_cost=0.0, financing_cost=0.0), '
            >>> res += 'tick_size=0.01), quantity=100, side=1)'
            >>> assert str(ex) == res
            >>>
            >>> fill = FillEvent(fill_cost=185.4, **info_dict)
            >>> res = res[:-1] + ', fill_cost=185.4)'
            >>> assert str(fill) == res.replace('ExecutionEvent', 'FillEvent')
        """
        super().__init__()
        self.timestamp = pd.Timestamp(timestamp)
        self.strategy = strategy
        self.asset = asset
        self.quantity = int(quantity)
        self.side = 1 if self.quantity > 0 else -1
        self.info = kwargs
        if self.quantity == 0: raise ValueError(
            f'[{self.__class__.__name__}] Invalid quantity of 0 '
            f'({strategy} / {asset.ticker} / {timestamp})'
        )

    def __init_subclass__(cls, event_type=None, **kwargs):
        """
        Default __init__ for sub-classes

        Args:
            event_type: event type
            **kwargs: pass to sub-classes
        """
        super().__init__(self=cls, **kwargs)


class OrderEvent(ExecutionEvent, event_type=EventType.ORDER):
    """
    Order details
    """


class MarketOrderEvent(OrderEvent, event_type=EventType.MKT_ORDER):
    """
    Market orders
    """
    def __init__(self, timestamp, strategy, asset: Asset, quantity, limit=None, **kwargs):
        super().__init__(
            timestamp=timestamp, strategy=strategy, asset=asset, quantity=quantity,
        )
        self.limit = round(float(limit), 2) if isinstance(limit, float) else None
        self.info = kwargs


class LimitOrderEvent(OrderEvent, event_type=EventType.LMT_ORDER):
    """
    Limit orders
    """
    def __init__(self, timestamp, strategy, asset: Asset, quantity, limit, **kwargs):
        super().__init__(
            timestamp=timestamp, strategy=strategy, asset=asset, quantity=quantity,
        )
        self.limit = round(float(limit), 2)
        self.info = kwargs


class FillEvent(ExecutionEvent, event_type=EventType.FILL):
    """
    Order fill details
    """
    def __init__(self, timestamp, strategy, asset: Asset, quantity, fill_cost, **kwargs):
        super().__init__(
            timestamp=timestamp, strategy=strategy, asset=asset, quantity=quantity,
        )
        self.fill_cost = round(float(fill_cost), 4)
        self.info = kwargs


if __name__ == '__main__':
    """
    CommandLine:
        python -m xzero.events.order all
    """
    import xdoctest
    xdoctest.doctest_module(__file__)
