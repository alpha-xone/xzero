from abc import ABCMeta, abstractmethod

from functools import wraps
from collections import namedtuple
from xone import utils
from xzero import ZeroBase

_COMM_SPLIT_ = '__'

TransCost = namedtuple('TransCost', ['total_comm', 'in_bps'])


def comms(cost, typ='dollar', **kwargs):
    """
    Generate commission subclass

    Args:
        cost: number or type + commission, e.g. 'dollar__20', 'per_share__5'
        typ: ['share', 'per_share', 'dollar', 'bps', 'trade', 'per_trade']
        **kwargs: passed into subclass instance

    Returns:
        Specified Commission subclass instance

    Examples:
        >>> Trans = namedtuple('Trans', ['quantity', 'fill_cost'])
        >>> t1 = Trans(quantity=16000, fill_cost=5.1)
        >>> t2 = Trans(quantity=1000, fill_cost=85.)
        >>> c1 = comms('dollar__15')
        >>> assert c1.calculate(t1) == TransCost(total_comm=122.4, in_bps=15.)
        >>> c2 = comms('trade__75')
        >>> assert c2.calculate(t1) == TransCost(total_comm=75., in_bps=9.19)
        >>> c3 = comms('share__5')
        >>> assert c3.calculate(t2) == TransCost(total_comm=50., in_bps=5.88)
    """
    args = []
    if isinstance(cost, str) and (_COMM_SPLIT_ in cost):
        typ, cost, *args = cost.split(_COMM_SPLIT_)

    for cls in Commission.__subclasses__():
        if cls.check_type(typ):
            if len(args) > 0: kwargs['min_cost'] = float(args[0])
            return cls(cost=cost, **kwargs)

    return PerShare(cost=cost)


def calc_comms(func):

    @wraps(func)
    def wrapper(self, transaction):

        if transaction.quantity == 0:
            return TransCost(in_bps=0., total_comm=0.)

        total_cost = round(max(func(self, transaction), self.min_cost), 2)
        total_amt = transaction.quantity * transaction.fill_cost
        return TransCost(
            total_comm=total_cost, in_bps=abs(round(total_cost / total_amt * 1e4, 2)),
        )

    return wrapper


class Commission(ZeroBase):
    """
    Commission specification and calculation

    Args:
        cost: number
    """
    __metaclass__ = ABCMeta

    def __init__(self, cost, min_cost=0):

        super().__init__()
        self.cost = round(float(cost) / 10 ** self.__dict__.get('rounding', 0.), 6)
        self.min_cost = round(float(min_cost), 2)

    def __init_subclass__(cls, keywords=None, **kwargs):

        cls.keywords = keywords
        cls.rounding = kwargs.pop('rounding', 0)
        super().__init_subclass__(**kwargs)

    @classmethod
    def check_type(cls, typ): return typ in cls.__dict__['keywords']

    def __repr__(self):

        return f'{self.__class__.__name__}({utils.to_str(self.__dict__)[1:-1]})'

    @abstractmethod
    def calculate(self, transaction):
        """
        Transaction costs

        Args:
            transaction: filled order

        Returns:
            Total costs
            Wrapper will calcualte total costs and costs in terms of bps
        """
        raise NotImplementedError('Should implement calculate()')


class PerShare(Commission, keywords=['share', 'per_share'], rounding=2):

    @calc_comms
    def calculate(self, transaction):
        return abs(transaction.quantity * self.cost)


class PerDollar(Commission, keywords=['dollar', 'bps'], rounding=4):
    """
    Cost parameter is the cost of a trade per-dollar. 0.0015
    on $1 million means $1,500 commission (=1,000,000 x 0.0015)
    """
    @calc_comms
    def calculate(self, transaction):
        return abs(transaction.quantity) * transaction.fill_cost * self.cost


class PerTrade(Commission, keywords=['trade', 'per_trade']):

    @calc_comms
    def calculate(self, transaction):
        return self.cost


if __name__ == '__main__':
    """
    CommandLine:
        python -m xzero.execution.commission all
    """
    import xdoctest
    xdoctest.doctest_module(__file__)
