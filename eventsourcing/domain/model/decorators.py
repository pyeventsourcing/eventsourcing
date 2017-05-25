from inspect import isfunction
from random import random
from time import sleep

from six import wraps

try:
    # Python 3.4+
    from functools import singledispatch
except ImportError:
    from singledispatch import singledispatch

from eventsourcing.domain.model.events import subscribe
from eventsourcing.exceptions import ProgrammingError


def subscribe_to(event_class):
    """
    Decorator for making a custom event handler function subscribe to a certain event type
    
    event_class: DomainEvent class or its child classes that the handler function should subscribe to

    The following example shows a custom handler that reacts to Todo.Created
    event and saves a projection of a Todo model object.
        
    .. code::
    
        @subscribe_to(Todo.Created)
        def new_todo_projection(event):
            todo = TodoProjection(id=event.originator_id, title=event.title)
            todo.save()
    """

    def event_type_predicate(event):
        return isinstance(event, event_class)

    def wrap(handler_func):
        subscribe(handler_func, event_type_predicate)
        return handler_func

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
            self.change_attribute(name=name, value=value)

        def new_getter(self):
            name = '_' + getter.__name__
            return getattr(self, name)

        return property(fget=new_getter, fset=setter, doc=getter.__doc__)
    else:
        raise ProgrammingError("Expected a function, got: {}".format(repr(getter)))


def retry(exc=Exception, max_retries=1, wait=0):
    def _retry(func):

        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while True:
                try:
                    result = func(*args, **kwargs)
                    sleep(0.01)
                    return result
                except exc:
                    attempts += 1
                    if attempts < max_retries:
                        sleep(wait * (1 + 0.1 * (random() - 0.5)))
                    else:
                        # Max retries exceeded.
                        raise

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
        if not isinstance(max_retries, int):
            raise TypeError("'max' must be an int: {}".format(max_retries))
        if not isinstance(wait, (float, int)):
            raise TypeError("'wait' must be a float: {}".format(max_retries))
        return _retry
