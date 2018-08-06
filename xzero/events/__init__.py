from enum import Enum, auto

from xzero import ZeroBase


class EventType(Enum):

    MARKET = auto()
    EXECUTION = auto()
    SIGNAL = auto()
    ORDER = auto()
    MKT_ORDER = auto()
    LMT_ORDER = auto()
    FILL = auto()


class Event(ZeroBase):
    """
    Base class for events that will flows through trading infrastructure

    Examples:
        >>> event = Event.from_dict(event_type='mkt')
        >>> assert str(event) == 'Event()'
    """
    def __init_subclass__(cls, event_type=None, **kwargs):
        cls.event_type = event_type
        super().__init_subclass__(**kwargs)


if __name__ == '__main__':
    """
    CommandLine:
        python -m xzero.events all
    """
    import xdoctest
    xdoctest.doctest_module(__file__)
