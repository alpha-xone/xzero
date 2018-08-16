import pandas as pd
import numpy as np

from xone import logs

from xzero.events import Event
from xzero.events.signal import SignalEvent
from xzero.events.order import MarketOrderEvent, LimitOrderEvent, FillEvent

from xzero.data_handler import MarketSnapshot

from xzero.execution import BaseEngine


class SimulationEngine(BaseEngine):
    """
    Engine for simulations
    """
    def __init__(self, events_queue, inst_exec: bool, trade_on: str):
        """
        Args:
            inst_exec: if instant execution enabled
            trade_on: valid inputs - ['price', 'bid_ask', 'bid_ask_1', ...]
        """
        super().__init__()
        self.inst_exec = inst_exec

        self.trade_on = trade_on
        if ('bid' in trade_on) and ('ask' in trade_on):
            lvl = trade_on[-1]
            if lvl.isdigit():
                self._buy_on_, self._sell_on_ = f'ask_{lvl}', f'bid_{lvl}'
            else:
                self._buy_on_, self._sell_on_ = 'ask', 'bid'
        else:
            self._sell_on_, self._sell_on_ = trade_on, trade_on

        self._timestamp_ = None
        self._snap_ = MarketSnapshot()
        self.events_queue = events_queue

        self._logger_ = logs.get_logger(SimulationEngine, types='stream')

    def update(self, event: Event):
        """
        Update market snapshot with market data events

        Args:
            event: market event
        """
        self._snap_.update(event=event)

    def on_signal(self, event: Event):
        """
        Put signal events into events queue

        Args:
            event: signal events
        """
        if not isinstance(event, SignalEvent): return
        order_type = LimitOrderEvent \
            if event.order_type.upper() == 'LMT' else MarketOrderEvent

        for n, (asset, quantity) in enumerate(event.order_quantity):
            if self.inst_exec:
                fill_cost = self._get_fill_price_(
                    timestamp=event.timestamp, ticker=asset.ticker, quantity=quantity
                )
                if np.isnan(fill_cost): continue
                self.events_queue.put(FillEvent(
                    timestamp=event.timestamp, strategy=event.strategy, asset=asset,
                    quantity=quantity, fill_cost=fill_cost, idx=n
                ))
            else:
                self.events_queue.put(order_type(
                    timestamp=event.timestamp, strategy=event.strategy, asset=asset,
                    quantity=quantity, limit=asset.price, idx=n
                ))

    def _get_fill_price_(self, timestamp, ticker, quantity, limit=None):
        """
        Get executed price for simulation
        """
        if quantity == 0:
            self._logger_.warning(f'{ticker}:quantity equals 0')
            return np.nan

        snap = self._snap_[ticker]
        field = self._buy_on_ if quantity > 0 else self._sell_on_
        if field not in snap:
            self._logger_.error(f'{ticker}:price field {field} not in market snapshot')
            return np.nan

        if np.isnan(snap[field]):
            self._logger_.warning(f'{ticker}:{field}:nan value')
            return np.nan

        if self.inst_exec and \
                (pd.Timestamp(timestamp) > pd.Timestamp(self._snap_.timestamp)):
            self._logger_.warning(
                f'{ticker}:order timestamp {timestamp} is later than '
                f'market snapshot timestamp {self._snap_.timestamp} in instance execution'
            )
            return np.nan

        if limit is None: return snap[field]
        if np.isnan(limit): return np.nan

        if (quantity > 0) and (limit <= snap[field]): return snap[field]
        if (quantity < 0) and (limit >= snap[field]): return snap[field]

        return np.nan

    def on_order(self, event: Event):
        """
        Order executions

        Args:
            event: order event
        """
        if not isinstance(event, (MarketOrderEvent, LimitOrderEvent)): return
        ticker = event.asset.ticker
        fill_cost = np.nan

        if isinstance(event, MarketOrderEvent):
            fill_cost = self._get_fill_price_(
                timestamp=event.timestamp, ticker=ticker,
                quantity=event.quantity, limit=None
            )

        if isinstance(event, LimitOrderEvent):
            limit = event.limit
            fill_cost = self._get_fill_price_(
                timestamp=event.timestamp, ticker=ticker,
                quantity=event.quantity, limit=limit
            )

        if ~np.isnan(fill_cost):
            self.events_queue.put(FillEvent(
                timestamp=self._snap_.timestamp, strategy=event.strategy,
                asset=event.asset, quantity=event.quantity,
                fill_cost=fill_cost, **event.info
            ))
