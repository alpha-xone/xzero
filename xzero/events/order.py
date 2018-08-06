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
        """
        super().__init__()
        self.strategy = strategy
        self.ticker = ticker
        self.datetime = timestamp
        self.quantity = int(quantity)
        self.side = 1 if self.quantity > 0 else -1
        self.info = kwargs
        if self.quantity == 0:
            raise ValueError(f'Invalid quantity of 0 for {strategy} / {ticker} / {timestamp}')

    def to_dict(self):
        return dict(**{
            k: v for k, v in self.__dict__.items() if k not in ['info']
        }, **self.info)


class SignalEvent(ExecutionEvent, event_type=EventType.SIGNAL):
    """
    Signal details
    """
    def __init__(self, strategy, ticker, timestamp, quantity, **kwargs):
        super().__init__(
            strategy=strategy, ticker=ticker, timestamp=timestamp,
            quantity=quantity, **kwargs
        )


class OrderEvent(ExecutionEvent, event_type=EventType.ORDER):
    """
    Order details
    """
    def __init__(self, strategy, ticker, timestamp, quantity, **kwargs):
        super().__init__(
            strategy=strategy, ticker=ticker, timestamp=timestamp,
            quantity=quantity, **kwargs
        )


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
