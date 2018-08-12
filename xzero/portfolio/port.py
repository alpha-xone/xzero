import numpy as np

from collections import defaultdict, namedtuple

from xzero import ZeroBase
from xzero.asset import Asset
from xzero.events.transaction import Transaction

from xone import logs

LongShort = namedtuple('LongShort', ['long', 'short'])
TargetTrade = namedtuple('TargetTrade', ['asset', 'quantity'])


class SubPortfolio(ZeroBase):
    """
    Sub-Portfolio to hold long / short pairs or a group of assets
    """
    def __init__(self, port_name):

        super().__init__()
        self.portfolio_name = port_name
        self.positions = defaultdict(Asset)

        self._logger_ = logs.get_logger(SubPortfolio, types='stream')

    @property
    def _market_value_(self):
        """
        Long and short exposures
        """
        long, short = 0., 0.
        for asset in self.positions.values():
            if asset.quantity > 0: long += asset.market_value
            elif asset.quantity < 0: short += asset.market_value
        return LongShort(long=long, short=short)

    @property
    def _quantity_(self):
        long, short = 0., 0.
        for asset in self.positions.values():
            if asset.quantity > 0: long += asset.quantity
            elif asset.quantity < 0: short += asset.quantity
        return LongShort(long=long, short=short)

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
        long, short = 0., 0.
        for asset in self.positions.values():
            if asset.quantity == 0: continue
            if asset.quantity != 0 and asset.margin_req == 0:
                self._logger_.warning(f'Margin requirment for {asset.ticker} is 0.')
                continue
            if asset.quantity > 0: long += asset.market_value * asset.margin_req
            elif asset.quantity < 0: short += asset.market_value * asset.margin_req
        return max(long, abs(short))

    @property
    def is_flat(self):
        """
        Whether the sub-portfolio is flattened
        """
        qty = self._quantity_
        return qty.long == 0 and qty.short == 0


class Portfolio(ZeroBase):
    """
    Portfolio tracking cash
    """
    def __init__(self, init_cash, **kwargs):

        super().__init__()
        self.init_cash = init_cash

        # Internal values to track positions and performance
        self._cash_ = init_cash
        self._market_value_ = 0.
        self._margin_ = 0.
        self._positions_ = defaultdict(Asset)
        self._sub_port_ = defaultdict(SubPortfolio)
        self._performance_ = []
        self._tolerance_ = kwargs.pop('tolerance', 5e5)

        self._logger_ = logs.get_logger(name_or_func=Portfolio, types='stream')

    def trade(self, port_name, target_value, snapshot, weights=None, *args):
        """
        Trade portfolio according (including taking risks and unwinds)

        Args:
            port_name: sub-portfolio name
            target_value: target value - accepts both positive and negative
            snapshot: market snapshot
            weights: weights of each component (dict)
            *args: list of assets
        """
        cur_port = self._sub_port_.get(port_name, SubPortfolio(port_name=port_name))
        cur_pos = cur_port.positions
        net_chg = abs(cur_port.exposure - target_value)
        weights = proper_weights(weights=weights, *args)

        if (net_chg < self._tolerance_) and (target_value != 0):
            self._logger_.info(
                f'Skip trading sub-portfolio [{port_name}] '
                f'cause delta change is too small: {net_chg}'
            )

        for asset in args:
            if np.isnan(snapshot[asset.ticker].price) and (weights.get(asset.ticker, 0) != 0):
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
            for asset in args:
                cur = cur_pos[asset.ticker]
                cur_val = cur.quantity * snapshot[cur.ticker].price * cur.lot_size
                trd_size[asset.ticker] = TargetTrade(asset=asset, quantity=round(
                    (target_value * weights[asset.ticker] - cur_val) / cur.lot_size
                ))

        # TODO: use margin requirements to adjust cash
        #       1) add back margins from the unwound portion
        #       2) use margins as cash constrains for trade initiations
        #       3) track margin changes every day

        # Check unwind positions
        for ticker, (asset, quantity) in trd_size.items():
            # Existing positions
            if asset.ticker not in cur_port.positions: cur_asset_pos = 0
            else: cur_asset_pos = cur_port.positions[asset.ticker].quantity

            # Positions to unwind
            unwind_pos = 0
            if quantity * cur_asset_pos < 0:
                unwind_pos = np.sign(cur_asset_pos) * min(quantity, cur_asset_pos)
            if unwind_pos == 0: continue

            # Transaction details
            trans = Transaction(
                port_name=port_name, asset=asset, snapshot=snapshot, quantity=unwind_pos
            )
            self._cash_ += trans.total_notional - trans.comm_total

            # Adjust new size for trades
            trd_size[ticker] = TargetTrade(asset=asset, quantity=quantity - unwind_pos)

        # Exit when there is no more trades
        left_val = np.array([
            asset.lot_size * qty * snapshot[asset.ticker] for asset, qty in trd_size.values()
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

            # Transaction details
            trans = Transaction(
                port_name=port_name, asset=asset, snapshot=snapshot, quantity=quantity
            )
            self._cash_ -= trans.total_notional - trans.comm_total

    def market_value(self, snapshot):
        """
        Latest market value of all current holdings
        Clean up sub-portfolio and positions that are already unwound

        Args:
            snapshot: market snapshot
        """
        mkt_val = 0.
        for asset in self._positions_.values():
            price = snapshot[asset.ticker].price
            if not np.isnan(price): asset.price = snapshot.price
            mkt_val += asset.market_value

        flat_port = [port for port, sub in self._sub_port_.items() if sub.is_flat]
        for port in flat_port: self._sub_port_.pop(port)

        flat_pos = [ticker for ticker, pos in self._positions_.items() if pos.quantity == 0]
        for ticker in flat_pos: self._positions_.pop(ticker)

        return mkt_val

    @property
    def margin(self):
        """
        Latest margin for all sub-portfolio
        """
        return np.array([port.margin for port in self._sub_port_.values()]).sum()


def proper_weights(weights=None, *args):
    """
    Normalize weights to be capped by 1 and keep long / short ratio

    Args:
        weights: initial weights
        *args: list of assets

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
        >>> assert proper_weights(w1, a1, a2, a3) == dict(AAPL=.5, GOOG=.5, FB=-.75)
        >>> assert proper_weights(w2, a1, a2, a3) == dict(AAPL=1., GOOG=-1.)
    """
    if weights is None:
        if len(args) == 2: weights = {args[0].ticker: 1., args[1]: -1.}
        elif len(args) == 1: weights = {args[0].ticker: 1.}

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
