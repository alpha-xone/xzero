import pandas as pd
import numpy as np

from copy import deepcopy
from collections import defaultdict, namedtuple, OrderedDict

from xzero import ZeroBase, show_value, show_qty
from xzero.asset import Asset
from xzero.events.transaction import Transaction

from xone import logs

LongShort = namedtuple('LongShort', ['long', 'short'])
TargetTrade = namedtuple('TargetTrade', ['asset', 'quantity'])


class SubPortfolio(ZeroBase):
    """
    Sub-Portfolio to hold long / short pairs or a group of assets
    """
    def __init__(self, pf_name):

        super().__init__()
        self.pf_name = pf_name
        self.positions = defaultdict(Asset)

        self._logger_ = logs.get_logger(SubPortfolio, types='stream')

    @property
    def _market_value_(self):
        """
        Long and short exposures
        """
        mkt_val = np.array([asset.market_value for asset in self.positions.values()])
        return LongShort(
            long=mkt_val[mkt_val > 0].sum(), short=abs(mkt_val[mkt_val < 0]).sum()
        )

    @property
    def _quantity_(self):

        qty = np.array([asset.quantity for asset in self.positions.values()])
        return LongShort(long=qty[qty > 0].sum(), short=abs(qty[qty < 0]).sum())

    @property
    def exposure(self):
        """
        Absolute value of one-sided expsoure
        """
        mkt_val = self._market_value_
        return max(mkt_val.long, abs(mkt_val.short))

    @property
    def side(self):
        """
        Side of the sub-portfolio
        Determined by the side of the first asset - NOT the net delta exposure
        """
        if len(self.positions) == 0: return 0
        return int(np.sign(list(self.positions.values())[0].quantity))

    @property
    def delta(self):
        """
        Delta between positive and negative positions

        Returns:
            Delta market values
        """
        mkt_val = self._market_value_
        return mkt_val.long + mkt_val.short

    @property
    def margin(self):
        """
        Assuming charged as max(long, short)
        """
        m = np.array([asset.market_value for asset in self.positions.values()])
        r = np.array([asset.margin_req for asset in self.positions.values()])

        if r.min() == 0:
            zero_req = [
                asset.ticker for asset in self.positions.values()
                if asset.margin_req == 0
            ]
            self._logger_.warning(f'margin requirements for tickers {zero_req} are 0')

        return max((m[m > 0] * r[m > 0]).sum(), abs(m[m < 0] * r[m < 0]).sum())

    @property
    def is_flat(self):
        """
        Whether the sub-portfolio is flattened
        """
        qty = self._quantity_
        return qty.long == 0 and qty.short == 0


class Portfolio(ZeroBase):
    """
    Portfolio tracking cash, positions, sub-portfolio, performance, risks and etc.

    Examples:
        >>> import pandas as pd
        >>> from xzero.asset import Equity
        >>>
        >>> a1 = Equity(ticker='AAPL', price=200., lot_size=100)
        >>> a2 = Equity(ticker='GOOG', price=1230, lot_size=100)
        >>> a3 = Equity(ticker='FB', price=180, lot_size=100)
        >>>
        >>> snapshot = dict()
        >>> snapshot['AAPL'] = pd.Series({'price': 210})
        >>> snapshot['GOOG'] = pd.Series({'price': 1220})
        >>> snapshot['FB'] = pd.Series({'price': 185})
        >>>
        >>> weights = {'AAPL': 1, 'GOOG': 1, 'FB': -1}
        >>>
        >>> p = Portfolio(init_cash=1e6)
        >>>
        >>> p.trade('tech', 1e6, snapshot, [a1, a2, a3], weights)
        >>>
        >>> assert p.mark_to_market(snapshot) == 492500
        >>> assert p.total_costs == 298.3
        >>> assert round(p.nav * p.init_cash / 100 + p.total_costs, 0) == 1e6
        >>> assert p.margin == 145800
        >>>
        >>> snapshot['AAPL'] = pd.Series(dict(price=220))
        >>> assert p.mark_to_market(snapshot) == 516500
        >>> assert p.nav == 102.3702
        >>>
        >>> snapshot['FB'] = pd.Series(dict(price=190))
        >>> assert p.mark_to_market(snapshot) == 503000
        >>> assert p.nav == 101.0202
        >>>
        >>> p.trade('tech', -5e5, snapshot, [a1, a2, a3], weights)
        >>> assert p.total_costs == 750.7
        >>> assert p.nav == 100.9749
        >>>
        >>> sub_port = p.__dict__['_sub_pf_']['tech']
        >>> assert sub_port.positions['AAPL'].quantity == -11
        >>> assert sub_port.positions['GOOG'].quantity == -2
        >>> assert sub_port.positions['FB'].quantity == 13
        >>>
        >>> assert p.margin == 69900
    """
    def __init__(self, init_cash, trade_on='price', mark_on='price', **kwargs):
        """
        Args:
            init_cash: initial cash
            trade_on: field to trade on
            mark_on: price field for mark-to-market purpose
            **kwargs: other kwargs for the class
        """
        super().__init__()
        self.init_cash = init_cash
        self.trade_on = trade_on
        self.mark_on = mark_on

        if trade_on in ['bid_ask', 'ask_bid']:
            self._buy_on_, self._sell_on_ = 'ask', 'bid'
        else:
            self._buy_on_, self._sell_on_ = trade_on, trade_on

        # Internal values to track positions and performance
        self._cash_ = init_cash
        self._commission_ = defaultdict(float)
        self._market_value_ = 0.
        self._margin_ = 0.
        self._positions_ = defaultdict(Asset)
        self._sub_pf_ = defaultdict(SubPortfolio)
        self._performance_ = []
        self._tolerance_ = kwargs.pop('tolerance', 5e5)
        self._cur_dt_ = None
        self.info = kwargs

        self._logger_ = logs.get_logger(Portfolio, types='stream', level='info')

    def perf(self):
        """
        Current performance
        """
        return dict(
            dt=self._cur_dt_, cash=self._cash_, market_value=self.market_value,
            margin=self.margin, sub_pf=self.sub_portfolio, pos=self.positions,
            long_mv=self.long_market_value, short_mv=self.short_market_value,
        )

    @property
    def positions(self):
        """
        Snapshot of current positions
        """
        return [dict(
            ticker=ticker, price=pos.price, quantity=pos.quantity, lot_size=pos.lot_size,
            market_value=pos.market_value, margin_req=pos.margin_req,
        ) for ticker, pos in self._positions_.items()]

    @property
    def sub_portfolio(self):
        """
        Snapshot of sub-portfolio
        """
        return list(np.array([[
            dict(
                pf_name=pf_name, ticker=ticker, price=pos.price, quantity=pos.quantity,
                lot_size=pos.lot_size, market_value=pos.market_value, margin=sub.margin,
            ) for ticker, pos in sub.positions.items()
        ] for pf_name, sub in self._sub_pf_.items()]).flatten())

    @property
    def frame_pos(self):
        """
        Position as DataFrame
        """
        return pd.DataFrame(pd.Series(self.positions).apply(OrderedDict).tolist())

    @property
    def frame_sub_pf(self):
        """
        Sub-portfolio as DataFrame
        """
        return pd.DataFrame(pd.Series(self.sub_portfolio).apply(OrderedDict).tolist())

    def trade(self, pf_name, target_value, snapshot, assets, weights=None):
        """
        Trade portfolio according (including taking risks and unwinds)

        Args:
            pf_name: sub-portfolio name
            target_value: target value - accepts both positive and negative
            snapshot: market snapshot
            assets: list of assets
            weights: weights of each component (dict)
        """
        cur_pf = self._sub_pf_.get(pf_name, SubPortfolio(pf_name=pf_name))
        cur_pos = cur_pf.positions
        net_chg = abs(cur_pf.exposure - target_value)
        weights = proper_weights(weights=weights, assets=assets)

        if (net_chg < self._tolerance_) and (target_value != 0):
            self._logger_.info(
                f'Skip trading sub-portfolio [{pf_name}] '
                f'cause delta change is too small: {net_chg}'
            )

        for asset in assets:
            buy_px = snapshot[asset.ticker][self._buy_on_]
            sell_px = snapshot[asset.ticker][self._sell_on_]
            if (np.isnan(buy_px) or np.isnan(sell_px)) and (weights.get(asset.ticker, 0) != 0):
                self._logger_.info(f'Cannot trade {asset.ticker} due to price availability')
                return

        trd_size = defaultdict(TargetTrade)
        if target_value == 0:
            # Unwind existing positions
            trd_size.update({
                asset.ticker: TargetTrade(asset=asset, quantity=-asset.quantity)
                for asset in cur_pos.values()
            })

        else:
            # Initiate new trades
            for asset in assets:
                ticker = asset.ticker
                price = snapshot[ticker][self.mark_on]
                cur_qty = cur_pos[ticker].quantity if ticker in cur_pos else 0
                cur_val = cur_qty * price * asset.lot_size
                trd_size[ticker] = TargetTrade(asset=asset, quantity=round(
                    (target_value * weights[ticker] - cur_val) / asset.lot_size / price
                ))
                self._logger_.debug(
                    f'{ticker}:target_value={show_value(target_value * weights[ticker])}:'
                    f'current_value={show_value(cur_val)}:'
                    f'quantity={show_qty(trd_size[ticker][1])}:'
                    f'order_value={show_value(trd_size[ticker][1] * asset.lot_size * price)}'
                )

        # TODO: use margin requirements to adjust cash
        #       1) add back margins from the unwound portion
        #       2) use margins as cash constrains for trade initiations
        #       3) track margin changes every day

        # Unwind positions if direction is different
        for ticker, (asset, quantity) in trd_size.items():
            # Existing positions
            if asset.ticker not in cur_pf.positions: cur_asset_pos = 0
            else: cur_asset_pos = cur_pf.positions[asset.ticker].quantity

            # Positions to unwind
            unwind_pos = 0
            if quantity * cur_asset_pos < 0:
                unwind_pos = np.sign(-cur_asset_pos) * min(abs(quantity), abs(cur_asset_pos))
            if unwind_pos == 0: continue

            self._execute_order_(
                pf_name=pf_name, asset=asset, snapshot=snapshot, quantity=unwind_pos
            )

            # Adjust new size for trades
            trd_size[ticker] = TargetTrade(asset=asset, quantity=quantity - unwind_pos)
            self._logger_.debug(
                f'{pf_name}:{ticker}:qty={show_qty(quantity)}:'
                f'unwind={show_qty(unwind_pos)}:new_qty={show_qty(quantity - unwind_pos)}'
            )

        # Exit when there is no more trades
        left_val = np.array([
            asset.lot_size * qty * snapshot[asset.ticker][self.mark_on]
            for asset, qty in trd_size.values()
        ])
        if abs(left_val).sum() == 0: return

        # Determine target values for new trades with cash constrains
        target_cap = LongShort(
            long=left_val[left_val > 0].sum(), short=left_val[left_val < 0].sum()
        )
        scale = max(target_cap.long, abs(target_cap.short)) / abs(self._cash_)

        # Enter new trades
        for ticker, (asset, quantity) in trd_size.items():
            if scale > 1.: quantity = round(quantity / scale, 0)
            if quantity == 0: continue
            self._execute_order_(
                pf_name=pf_name, asset=asset, quantity=quantity, snapshot=snapshot
            )

    def _execute_order_(self, pf_name, asset: Asset, quantity, snapshot):
        """
        Execute given order and adjust cash, commissions and etc.

        Args:
            pf_name: sub-portfolio name
            asset: asset
            quantity: order quantity
            snapshot: market snapshot
        """
        ticker = asset.ticker
        trans = Transaction(
            port_name=pf_name, asset=asset, snapshot=snapshot, quantity=quantity,
            trade_on=self._buy_on_ if quantity > 0 else self._sell_on_,
        )

        cash_info = f'{pf_name}:{ticker}:cash={show_value(self._cash_)}:' \
                    f'notional={show_value(trans.total_notional)}:' \
                    f'comms={show_value(trans.comm_total)}'
        self._cash_ -= round(trans.total_notional + trans.comm_total, 2)
        self._commission_[ticker] += round(trans.comm_total, 2)
        self._logger_.debug(f'{cash_info}:after={show_value(self._cash_)}')

        cur_qty = self._positions_[ticker].quantity if ticker in self._positions_ else 0
        pos_info = f'{pf_name}:{ticker}:quantity={show_qty(cur_qty)}:chg={show_qty(quantity)}'
        self._update_position_(pf_name=pf_name, asset=asset, quantity=quantity)
        self._logger_.debug(f'{pos_info}:after={show_qty(self._positions_[ticker].quantity)}')

    def _update_position_(self, pf_name, asset: Asset, quantity):
        """
        Update positions of sub-portfolio and self positions together

        Args:
            pf_name: sub-portfolio name
            asset: asset
            quantity: change of quantities, - / +
        """
        ticker = asset.ticker
        if pf_name not in self._sub_pf_:
            self._sub_pf_[pf_name] = SubPortfolio(pf_name=pf_name)

        cur_pf = self._sub_pf_[pf_name]
        if ticker not in cur_pf.positions:
            cur_pf.positions[ticker] = asset
            cur_pf.positions[ticker].quantity = quantity
        else:
            cur_pf.positions[ticker].quantity += quantity

        cur_pos = self._positions_
        if ticker not in cur_pos:
            cur_pos[ticker] = deepcopy(asset)
            cur_pos[ticker].quantity = quantity
        else:
            cur_pos[ticker].quantity += quantity

    @property
    def nav(self):
        """
        Current total market values
        """
        return round((self._cash_ + self.market_value) / self.init_cash * 100, 4)

    @property
    def _mkt_val_(self):
        """
        Market values for all underlying assets as list
        """
        return np.array([asset.market_value for asset in self._positions_.values()])

    @property
    def long_market_value(self):
        """
        Long market value
        """
        mkt_val = self._mkt_val_
        return mkt_val[mkt_val > 0].sum()

    @property
    def short_market_value(self):
        """
        Short market value
        """
        mkt_val = self._mkt_val_
        return mkt_val[mkt_val < 0].sum()

    @property
    def market_value(self):
        """
        Net market value of all current positions
        """
        return self._mkt_val_.sum()

    def mark_to_market(self, snapshot=None):
        """
        Clean up sub-portfolio and positions that are already unwound
        Refresh latest market value of all current holdings

        Args:
            snapshot: market snapshot

        Returns:
            Net market value
        """
        flat_pf = [port for port, sub in self._sub_pf_.items() if sub.is_flat]
        for pf in flat_pf: self._sub_pf_.pop(pf)

        flat_pos = [ticker for ticker, pos in self._positions_.items() if pos.quantity == 0]
        for ticker in flat_pos: self._positions_.pop(ticker)

        mkt_val = 0.
        for asset in self._positions_.values():
            if snapshot is not None:
                price = snapshot[asset.ticker][self.mark_on]
                if not np.isnan(price): asset.price = price
            mkt_val += asset.market_value

        return mkt_val

    @property
    def total_costs(self):
        """
        Total costs of commission (to add financings later)
        """
        return round(np.array(list(self._commission_.values())).sum(), 2)

    @property
    def margin(self):
        """
        Latest margin for all sub-portfolio
        """
        return np.array([pf.margin for pf in self._sub_pf_.values()]).sum()


def proper_weights(assets, weights=None):
    """
    Normalize weights to be capped by 1 and keep long / short ratio

    Args:
        assets: list of assets
        weights: dict of initial weights

    Returns:
        dict: weight of each asset

    Examples:
        >>> from xzero.asset import Equity
        >>>
        >>> a1 = Equity(ticker='AAPL', price=200., lot_size=100)
        >>> a2 = Equity(ticker='GOOG', price=1230, lot_size=100)
        >>> a3 = Equity(ticker='FB', price=180, lot_size=100)
        >>>
        >>> w1 = dict(AAPL=200, GOOG=200, FB=-300)
        >>> w2 = dict(AAPL=200, GOOG=-200)
        >>>
        >>> assert proper_weights([a1, a2, a3], w1) == dict(AAPL=.5, GOOG=.5, FB=-.75)
        >>> assert proper_weights([a1, a2, a3], w2) == dict(AAPL=1., GOOG=-1.)
    """
    if weights is None:
        if len(assets) == 2: weights = {assets[0].ticker: 1., assets[1]: -1.}
        elif len(assets) == 1: weights = {assets[0].ticker: 1.}

    else:
        # Normalized weights
        w_val = np.array([w for w in weights.values()])
        pos = w_val[w_val > 0].sum()
        neg = w_val[w_val < 0].sum()
        pos_to_neg = (pos / abs(neg)) if neg < 0 < pos else 1.

        for ticker, weight in weights.items():
            if weight == 0: continue
            weights[ticker] = weight / (pos if weight > 0 else (abs(neg) * pos_to_neg))

    return weights


if __name__ == '__main__':
    """
    CommandLine:
        python -m xzero.portfolio.port all
    """
    import xdoctest
    xdoctest.doctest_module(__file__)
