from xone import logs

from xzero.events import Event, EventType
from xzero.asset import Asset

from collections import namedtuple

Trans = namedtuple('Trans', ['quantity', 'fill_cost'])


class Transaction(Event, event_type=EventType.TRANSACTION):
    """
    Transaction details
    """
    def __init__(self, port_name, asset, snapshot, quantity):

        super().__init__()
        assert isinstance(asset, Asset)

        self.port_name = port_name
        self.ticker = asset.ticker
        self.price = snapshot[self.ticker].price
        self.lot_size = asset.lot_size
        self.quantity = quantity

        self._comms_ = asset.comms.calculate(transaction=Trans(
            quantity=quantity * self.lot_size, fill_cost=self.price
        ))
        self._logger_ = logs.get_logger(Transaction, types='stream')

        self.total_notional = round(self.price * self.lot_size * quantity, 2)
        self.comm_total = self._comms_.total_comm
        self.comm_in_bps = self._comms_.in_bps

        self._logger_.info(
            f'portfolio={port_name}:ticker={self.ticker}:'
            f'cost={self.price}:total_notional={self.total_notional}:'
            f'comms={self.comm_total}:in_bps={self.comm_in_bps}'
        )
