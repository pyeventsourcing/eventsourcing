from functools import singledispatch, wraps
from inspect import isfunction
from random import random
from time import sleep

from eventsourcing.domain.model.events import subscribe
from eventsourcing.exceptions import ProgrammingError


def subscribe_to(*event_classes):
    """
    Decorator for making a custom event handler function subscribe to a certain class of event.

    The decorated function will be called once for each matching event that is published, and will
    be given one argument, the event, when it is called. If events are published in lists, for
    example the AggregateRoot publishes a list of pending events when its __save__() method is called,
    then the decorated function will be called once for each event that is an instance of the given event_class.

    Please note, this decorator isn't suitable for use with object class methods. The decorator receives
    in Python 3 an unbound function, and defines a handler which it subscribes that calls the decorated
    function for each matching event. However the method isn't called on the object, so the object instance
    is never available in the decorator, so the decorator can't call a normal object method because it
    doesn't have a value for 'self'.

    event_class: type used to match published events, an event matches if it is an instance of this type

    The following example shows a custom handler that reacts to Todo.Created
    event and saves a projection of a Todo model object.

    .. code::

        @subscribe_to(Todo.Created)
        def new_todo_projection(event):
            todo = TodoProjection(id=event.originator_id, title=event.title)
            todo.save()
    """
    event_classes = list(event_classes)

    def wrap(func):
        def handler(event):
            if isinstance(event, (list, tuple)):
                for e in event:
                    handler(e)
            elif not event_classes or isinstance(event, tuple(event_classes)):
                func(event)

        subscribe(handler=handler, predicate=lambda _: True)
        return func

    if len(event_classes) == 1 and isfunction(event_classes[0]):
        func = event_classes.pop()
        return wrap(func)
    else:
        return wrap


def mutator(arg=None):
    """Structures mutator functions by allowing handlers
    to be registered for different types of event. When
    the decorated function is called with an initial
    value and an event, it will call the handler that
    has been registered for that type of event.

    It works like singledispatch, which it uses. The
    difference is that when the decorated function is
    called, this decorator dispatches according to the
    type of last call arg, which fits better with reduce().
    The builtin Python function reduce() is used by the
    library to replay a sequence of events against an
    initial state. If a mutator function is given to reduce(),
    along with a list of events and an initializer, reduce()
    will call the mutator function once for each event in the
    list, but the initializer will be the first value, and the
    event will be the last argument, and we want to dispatch
    according to the type of the event. It happens that
    singledispatch is coded to switch on the type of the first
    argument, which makes it unsuitable for structuring a mutator
    function without the modifications introduced here.

    The other aspect introduced by this decorator function is the
    option to set the type of the handled entity in the decorator.
    When an entity is replayed from scratch, in other words when
    all its events are replayed, the initial state is None. The
    handler which handles the first event in the sequence will
    probably construct an object instance. It is possible to write
    the type into the handler, but that makes the entity more difficult
    to subclass because you will also need to write a handler for it.
    If the decorator is invoked with the type, when the initial
    value passed as a call arg to the mutator function is None,
    the handler will instead receive the type of the entity, which
    it can use to construct the entity object.

    .. code::

        class Entity(object):
            class Created(object):
                pass

        @mutator(Entity)
        def mutate(initial, event):
            raise NotImplementedError(type(event))

        @mutate.register(Entity.Created)
        def _(initial, event):
            return initial(**event.__dict__)

        entity = mutate(None, Entity.Created())
    """

    domain_class = None

    def _mutator(func):
        wrapped = singledispatch(func)

        @wraps(wrapped)
        def wrapper(initial, event):
            initial = initial or domain_class
            return wrapped.dispatch(type(event))(initial, event)

        wrapper.register = wrapped.register

        return wrapper

    if isfunction(arg):
        return _mutator(arg)
    else:
        domain_class = arg
        return _mutator


def attribute(getter):
    """
    When used as a method decorator, returns a property object
    with the method as the getter and a setter defined to call
    instance method change_attribute(), which publishes an
    AttributeChanged event.
    """
    if isfunction(getter):
        def setter(self, value):
            name = '_' + getter.__name__
            self.__change_attribute__(name=name, value=value)

        def new_getter(self):
            name = '_' + getter.__name__
            return getattr(self, name, None)

        return property(fget=new_getter, fset=setter, doc=getter.__doc__)
    else:
        raise ProgrammingError("Expected a function, got: {}".format(repr(getter)))


def retry(exc=Exception, max_attempts=1, wait=0, stall=0, verbose=False):
    def _retry(func):

        @wraps(func)
        def wrapper(*args, **kwargs):
            if stall:
                sleep(stall)
            attempts = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exc as e:
                    attempts += 1
                    if max_attempts is None or attempts < max_attempts:
                        sleep(wait * (1 + 0.1 * (random() - 0.5)))
                        if verbose:
                            print("Retrying {}".format(func))
                    else:
                        # Max retries exceeded.
                        raise e

        return wrapper

    # If using decorator in bare form, the decorated
    # function is the first arg, so check 'exc'.
    if isfunction(exc):
        # Remember the given function.
        _func = exc
        # Set 'exc' to a sensible exception class for _retry().
        exc = Exception
        # Wrap and return.
        return _retry(func=_func)
    else:
        # Check decorator args, and return _retry,
        # to be called with the decorated function.
        if isinstance(exc, (list, tuple)):
            for _exc in exc:
                if not (isinstance(_exc, type) and issubclass(_exc, Exception)):
                    raise TypeError("not an exception class: {}".format(_exc))
        else:
            if not (isinstance(exc, type) and issubclass(exc, Exception)):
                raise TypeError("not an exception class: {}".format(exc))
        if not isinstance(max_attempts, int):
            raise TypeError("'max_attempts' must be an int: {}".format(max_attempts))
        if not isinstance(wait, (float, int)):
            raise TypeError("'wait' must be a float: {}".format(max_attempts))
        return _retry
