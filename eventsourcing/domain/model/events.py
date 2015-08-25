import itertools
from eventsourcing.utils.time import utc_now


class DomainEvent(object):

    def __init__(self, timestamp=None, **kwargs):
        self.__dict__['timestamp'] = utc_now() if timestamp is None else timestamp
        self.__dict__.update(kwargs)

    def __setattr__(self, key, value):
        raise AttributeError("DomainEvent attributes are read-only")

    @property
    def timestamp(self):
        return self.__dict__['timestamp']

    def __eq__(self, rhs):
        if type(self) is not type(rhs):
            return NotImplemented
        return self.__dict__ == rhs.__dict__

    def __ne__(self, rhs):
        return not (self == rhs)

    def __hash__(self):
        return hash(tuple(itertools.chain(self.__dict__.items(), [type(self)])))

    def __repr__(self):
        return self.__class__.__qualname__ + "(" + ', '.join(
            "{0}={1!r}".format(*item) for item in sorted(self.__dict__.items())) + ')'


_event_handlers = {}


def subscribe(event_predicate, subscriber):
    if event_predicate not in _event_handlers:
        _event_handlers[event_predicate] = []
    _event_handlers[event_predicate].append(subscriber)


def unsubscribe(event_predicate, subscriber):
    if event_predicate in _event_handlers:
        handlers = _event_handlers[event_predicate]
        if subscriber in handlers:
            handlers.remove(subscriber)


def publish(event):
    matching_handlers = []
    for event_predicate, handlers in _event_handlers.items():
        if event_predicate(event):
            for handler in handlers:
                if handler not in matching_handlers:
                    matching_handlers.append(handler)
    for handler in matching_handlers:
        handler(event)
