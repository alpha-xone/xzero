from abc import ABCMeta, abstractmethod

from xzero import ZeroBase
from xzero.events import Event


class BaseEngine(ZeroBase):
    """
    Abstract class of simulation / execution engine
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def update(self, event: Event):
        raise NotImplementedError('Should implement update(event)')

    @abstractmethod
    def on_order(self, event: Event):
        raise NotImplementedError('Should implement on_order(event)')

    @abstractmethod
    def on_signal(self, event: Event):
        raise NotImplementedError('Should implement on_signal(event)')
