import pandas as pd

from collections import defaultdict

from xzero import ZeroBase
from xzero.events import Event
from xzero.events.market import MarketEvent


class MarketSnapshotRow(ZeroBase):
    """
    Line items of market snapshots
    """
    def __init__(self, event=None):

        super().__init__()
        self.timestamp = None
        self.snapshot = dict()

        if isinstance(event, MarketEvent):
            self.timestamp = event.timestamp
            self.snapshot.update(**event.data.to_dict())

    def update(self, event):
        """
        Update snapshot according to latest market event

        Args:
            event: market event
        """
        if not isinstance(event, MarketEvent): return
        self.timestamp = pd.Timestamp(event.timestamp) \
            if isinstance(event.timestamp, str) else event.timestamp
        self.snapshot.update(event.data.to_dict())

    def __getattr__(self, item):

        return self.snapshot.get(item, None)

    def __getitem__(self, item):

        return self.snapshot.get(item, None)


class MarketSnapshot(ZeroBase):
    """
    Stores market snapshots
    """
    def __init__(self):

        super().__init__()
        self.timestamp = None
        self.snapshot = defaultdict(MarketSnapshotRow)

    def __getitem__(self, item):

        return self.snapshot.get(item, MarketSnapshotRow())

    def update(self, event: Event):
        """
        Update snapshot according to latest market event

        Args:
            event: market event
        """
        if not isinstance(event, MarketEvent): return

        # Keeps track of latest timestamps
        if self.timestamp is None: self.timestamp = event.timestamp
        elif self.timestamp < event.timestamp: self.timestamp = event.timestamp

        if isinstance(event.data, pd.Series):
            if event.ticker not in self.snapshot:
                self.snapshot[event.ticker] = MarketSnapshotRow(event=event)
            else:
                self.snapshot[event.ticker].update(event)

        elif isinstance(event.data, pd.DataFrame):
            for _, snap in event.data.iteritems():
                if snap.ticker not in self.snapshot:
                    self.snapshot[snap.ticker] = MarketSnapshotRow(
                        event=MarketEvent(timestamp=_, data=snap)
                    )
                else:
                    self.snapshot[snap.ticker].snapshot.update(**snap.to_dict())
