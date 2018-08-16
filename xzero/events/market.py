from xzero.events import Event, EventType


class MarketEvent(Event, event_type=EventType.MARKET):
    """
    Event for market data updates
    """
    def __init__(self, timestamp, data, ticker_field='ticker'):

        super().__init__()
        self.timestamp = timestamp
        self.ticker = data[ticker_field]
        self.data = data
