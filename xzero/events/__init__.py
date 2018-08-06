from enum import Enum, auto


class EventType(Enum):

    MARKET = auto()
    EXECUTION = auto()
    SIGNAL = auto()
    ORDER = auto()
    FILL = auto()


class Event(object):
    """
    Base class for events that will flows through trading infrastructure
    """
    def __init__(self, **kwargs):
        pass

    def __init_subclass__(cls, event_type=None, **kwargs):
        cls.event_type = event_type
        super().__init_subclass__(**kwargs)

    @classmethod
    def from_dict(cls, **event_dict):
        return cls(**event_dict)
