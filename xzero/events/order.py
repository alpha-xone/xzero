import pandas as pd

from abc import ABCMeta
from xzero.events import Event, EventType


class ExecutionEvent(Event, event_type=EventType.EXECUTION):
    """
    Base class for Signal, Order and Fill events
    """
    __metaclass__ = ABCMeta

    def __init__(self, strategy, ticker, timestamp, quantity, **kwargs):
        """
        Args:
            strategy: order strategy - helps grouping pairs / sub-strategies together
            ticker: ticker name
            timestamp: timestamp of event
            quantity: quantity to trade or filled
            **kwargs: other infomation

        Examples:
            >>> info_dict = dict(strategy='Growth', ticker='AAPL', timestamp='2018-07-05', quantity=100)
            >>> ex = ExecutionEvent.from_dict(**info_dict)
            >>> res = 'ExecutionEvent(strategy=Growth, ticker=AAPL, '
            >>> res += 'timestamp=2018-07-05 00:00:00, quantity=100, side=1)'
            >>> assert str(ex) == res
            >>>
            >>> signal = SignalEvent(**info_dict)
            >>> assert str(signal) == res.replace('ExecutionEvent', 'SignalEvent')
            >>>
            >>> fill = FillEvent(fill_cost=185.4, **info_dict)
            >>> res = res[:-1] + ', fill_cost=185.4)'
            >>> assert str(fill) == res.replace('ExecutionEvent', 'FillEvent')
        """
        super().__init__()
        self.strategy = strategy
        self.ticker = ticker
        self.timestamp = pd.Timestamp(timestamp)
        self.quantity = int(quantity)
        self.side = 1 if self.quantity > 0 else -1
        self.info = kwargs
        if self.quantity == 0: raise ValueError(
            f'[{self.__class__.__name__}] Invalid quantity of 0 '
            f'for {strategy} / {ticker} / {timestamp}'
        )

    def __init_subclass__(cls, event_type=None, **kwargs):
        """
        Default __init__ for sub-classes

        Args:
            event_type: event type
            **kwargs: pass to sub-classes
        """
        super().__init__(self=cls, **kwargs)


class SignalEvent(ExecutionEvent, event_type=EventType.SIGNAL):
    """
    Signal details
    """


class OrderEvent(ExecutionEvent, event_type=EventType.ORDER):
    """
    Order details
    """


class MarketOrderEvent(OrderEvent, event_type=EventType.MKT_ORDER):
    """
    Market orders
    """


class LimitOrderEvent(OrderEvent, event_type=EventType.LMT_ORDER):
    """
    Limit orders
    """
    def __init__(self, strategy, ticker, timestamp, quantity, limit, **kwargs):
        super().__init__(
            strategy=strategy, ticker=ticker, timestamp=timestamp, quantity=quantity
        )
        self.limit = round(float(limit), 2)
        self.info = kwargs


class FillEvent(ExecutionEvent, event_type=EventType.FILL):
    """
    Order fill details
    """
    def __init__(self, strategy, ticker, timestamp, quantity, fill_cost, **kwargs):
        super().__init__(
            strategy=strategy, ticker=ticker, timestamp=timestamp, quantity=quantity
        )
        self.fill_cost = round(float(fill_cost), 6)
        self.info = kwargs


if __name__ == '__main__':
    """
    CommandLine:
        python -m xzero.events.order all
    """
    import xdoctest
    xdoctest.doctest_module(__file__)
