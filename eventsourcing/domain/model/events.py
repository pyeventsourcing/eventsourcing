from abc import ABCMeta
import itertools
from six import with_metaclass
from eventsourcing.utils.time import utc_now


class QualnameABCMeta(ABCMeta):
    """Supplies __qualname__ to object classes with this metaclass.
    """
    __outer_classes = {}

    if not hasattr(object, '__qualname__'):

        def __init__(cls, name, bases, dict):
            super(QualnameABCMeta, cls).__init__(name, bases, dict)
            QualnameABCMeta.__outer_classes[cls] = None
            for class_attr in dict.values():  # iterate class attributes
                for outer_class in QualnameABCMeta.__outer_classes:
                    if class_attr == outer_class:  # is the object an already registered type?
                        QualnameABCMeta.__outer_classes[outer_class] = cls
                        break

        @property
        def __qualname__(cls):
            c = QualnameABCMeta.__outer_classes[cls]
            if c is None:
                return cls.__name__
            else:
                return "%s.%s" % (c.__qualname__, cls.__name__)



class DomainEvent(with_metaclass(QualnameABCMeta)):

    def __init__(self, entity_id=None, entity_version=None, timestamp=None, **kwargs):
        assert entity_id is not None
        assert entity_version is not None
        self.__dict__['entity_id'] = entity_id
        self.__dict__['entity_version'] = entity_version
        self.__dict__['timestamp'] = utc_now() if timestamp is None else timestamp
        self.__dict__.update(kwargs)

    def __setattr__(self, key, value):
        raise AttributeError("DomainEvent attributes are read-only")

    @property
    def entity_id(self):
        return self.__dict__['entity_id']

    @property
    def entity_version(self):
        return self.__dict__['entity_version']

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
        return hash(tuple(itertools.chain(sorted(self.__dict__.items()), [type(self)])))

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
