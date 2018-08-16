from collections import defaultdict

from xone import utils
from xzero import ZeroBase
from xzero.events import Event
from xzero.events.market import MarketEvent


class MarketSnapshotRow(ZeroBase):
    """
    Line items of market snapshots
    """
    def __init__(self):
        super().__init__()
        self.__dict__ = utils.AttributeDict()

    def update(self, event):
        """
        Update snapshot according to latest market event

        Args:
            event: market event
        """
        if not isinstance(event, MarketEvent): return
        self.__dict__.update(event.to_dict())


class MarketSnapshot(ZeroBase):
    """
    Stores market snapshots
    """
    def __init__(self):
        super().__init__()
        self.snap = defaultdict(MarketSnapshotRow)
        self.timestamp = None

    def update(self, event: Event):
        """
        Update snapshot according to latest market event

        Args:
            event: market event
        """
        if not isinstance(event, MarketEvent): return
        self.snap = event.data

    def __getitem__(self, item):

        return self.snap.get(item, MarketSnapshotRow())
