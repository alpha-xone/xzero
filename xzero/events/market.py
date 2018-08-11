from xzero.events import Event, EventType


class MarketEvent(Event, event_type=EventType.MARKET):
    """
    Event for market updates
    """
    def __init__(self, data):
        super().__init__()
        self.data = data
        self.timestamp = None
