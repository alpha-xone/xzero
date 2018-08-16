from xzero.events import Event, EventType


class MarketEvent(Event, event_type=EventType.MARKET):
    """
    Event for market data updates
    """
    def __init__(self, timestamp, data, tck_fld='ticker'):

        super().__init__()
        self.timestamp = timestamp
        self.ticker = data[tck_fld]
        self.data = data
