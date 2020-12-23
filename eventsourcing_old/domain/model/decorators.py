import random
from functools import singledispatch, wraps
from inspect import isfunction
from time import sleep
from typing import Callable, Dict, Optional, Sequence, Type, Union, no_type_check

from eventsourcing.domain.model.events import DomainEvent, subscribe
from eventsourcing.exceptions import ProgrammingError


def subscribe_to(*args: Union[Callable, Type[DomainEvent]]) -> Callable:
    """
    Decorator for making a custom event handler function subscribe to a certain class
    of event.

    The decorated function will be called once for each matching event that is
    published, and will
    be given one argument, the event, when it is called. If events are published in
    lists, for
    example the AggregateRoot publishes a list of pending events when its __save__()
    method is called,
    then the decorated function will be called once for each event that is an
    instance of the given event_class.

    Please note, this decorator isn't suitable for use with object class methods. The
    decorator receives
    in Python 3 an unbound function, and defines a handler which it subscribes that
    calls the decorated
    function for each matching event. However the method isn't called on the object,
    so the object instance
    is never available in the decorator, so the decorator can't call a normal object
    method because it
    doesn't have a value for 'self'.

    :param event_class: type used to match published events, an event matches if it
      is an instance of this type.

    The following example shows a custom handler that reacts to Todo.Created
    event and saves a projection of a Todo model object.

    .. code::

        @subscribe_to(Todo.Created)
        def new_todo_projection(event):
            todo = TodoProjection(id=event.originator_id, title=event.title)
            todo.save()
    """

    @no_type_check
    def wrap(func):
        def handler(event):
            if isinstance(event, (list, tuple)):
                # Call handler once for each event.
                for e in event:
                    handler(e)
            elif not args or isinstance(event, args):
                # Call handler if there are no classes or have an instance.
                func(event)

        subscribe(handler=handler, predicate=lambda _: True)
        return func

    if len(args) == 1 and isfunction(args[0]):
        func = args[0]
        args = ()
        return wrap(func)
    else:
        return wrap


def mutator(arg: Optional[Callable] = None) -> Callable:
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

    @no_type_check
    def _mutator(func):
        wrapped = singledispatch(func)

        @wraps(wrapped)
        def wrapper(initial, event):
            initial = initial or domain_class
            return wrapped.dispatch(type(event))(initial, event)

        wrapper.register = wrapped.register

        return wrapper

    if not isfunction(arg):
        # Decorator used with an entity class.
        domain_class = arg
        return _mutator
    else:
        # Decorator invoked as method or function decorator.
        return _mutator(arg)


def attribute(getter: Callable) -> property:
    """
    When used as a method decorator, returns a property object
    with the method as the getter and a setter defined to call
    instance method __change_attribute__(), which publishes an
    AttributeChanged event.
    """
    if isfunction(getter):

        @no_type_check
        def setter(self, value):
            name = "_" + getter.__name__
            self.__change_attribute__(name=name, value=value)

        @no_type_check
        def new_getter(self):
            name = "_" + getter.__name__
            return getattr(self, name, None)

        return property(fget=new_getter, fset=setter, doc=getter.__doc__)
    else:
        raise ProgrammingError("Expected a function, got: {}".format(repr(getter)))


def retry(
    exc: Union[Type[Exception], Sequence[Type[Exception]]] = Exception,
    max_attempts: int = 1,
    wait: float = 0,
    stall: float = 0,
    verbose: bool = False,
) -> Callable:
    """
    Retry decorator.

    :param exc: List of exceptions that will cause the call to be retried if raised.
    :param max_attempts: Maximum number of attempts to try.
    :param wait: Amount of time to wait before retrying after an exception.
    :param stall: Amount of time to wait before the first attempt.
    :param verbose: If True, prints a message to STDOUT when retries occur.
    :return: Returns the value returned by decorated function.
    """

    @no_type_check
    def _retry(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if stall:
                sleep(stall)
            attempts = 0
            while True:
                try:
                    if verbose and attempts > 0:
                        print("Retrying ", func, args, kwargs)
                    return func(*args, **kwargs)
                except exc as e:
                    if verbose:
                        print("Error trying ", func, args, kwargs, e)
                    attempts += 1
                    if max_attempts is None or attempts < max_attempts:
                        sleep(wait * (1 + 0.1 * (random.random() - 0.5)))
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


def subclassevents(cls: type) -> type:
    """
    Decorator that avoids "boilerplate" subclassing of domain events.

    For example, with this decorator you can do this:

    .. code::

        @subclassevents
        class Example(AggregateRoot):
            class SomethingHappened(DomainEvent): pass

    rather than this:

    .. code::

        class Example(AggregateRoot):
            class Event(AggregateRoot.Event): pass
            class Created(Event, AggregateRoot.Created): pass
            class Discarded(Event, AggregateRoot.Discarded): pass
            class AttributeChanged(Event, AggregateRoot.AttributeChanged): pass
            class SomethingHappened(Event): pass

    You can apply this to a tree of domain event classes by defining
    the base class with attribute 'subclassevents = True'.
    """

    bases_event_attrs = []
    super_event_class_names = set()
    for base_cls in cls.__bases__:
        base_event_attrs: Dict[str, Type[DomainEvent]] = {}
        bases_event_attrs.append(base_event_attrs)
        for base_attr_name in dir(base_cls):
            base_attr = getattr(base_cls, base_attr_name)
            if isinstance(base_attr, type) and issubclass(base_attr, DomainEvent):
                base_event_attrs[base_attr_name] = base_attr
                if base_attr_name != "Event":
                    super_event_class_names.add(base_attr_name)

    # Define base Event subclass including super Event classes.
    if "Event" in cls.__dict__:
        event_event_subclass = cls.__dict__["Event"]
    else:
        base_event_classes = []
        for base_event_attrs in bases_event_attrs:
            try:
                event_cls = base_event_attrs["Event"]
            except KeyError:
                pass
            else:
                base_event_classes.append(event_cls)

        event_event_subclass = type(
            "Event",
            tuple(base_event_classes or [DomainEvent]),
            {"__qualname__": cls.__name__ + ".Event"},
        )
        event_event_subclass.__module__ = cls.__module__
        setattr(cls, "Event", event_event_subclass)

    # Define subclasses for super event classes, including Event subclass as base.
    for super_event_class_name in super_event_class_names:

        base_event_classes = [event_event_subclass]
        if super_event_class_name in cls.__dict__:
            continue

        for base_event_attrs in bases_event_attrs:
            try:
                event_cls = base_event_attrs[super_event_class_name]
            except KeyError:
                pass
            else:
                base_event_classes.append(event_cls)
        event_subclass = type(
            super_event_class_name,
            tuple(base_event_classes),
            {"__qualname__": cls.__name__ + "." + super_event_class_name},
        )
        event_subclass.__module__ = cls.__module__
        setattr(cls, super_event_class_name, event_subclass)

    # Redefine event classes in cls.__dict__ that are not subclasses of Event.
    for cls_attr_name in cls.__dict__.keys():
        cls_attr = getattr(cls, cls_attr_name)
        if isinstance(cls_attr, type) and issubclass(cls_attr, DomainEvent):
            if not issubclass(cls_attr, event_event_subclass):
                try:
                    event_subclass = type(
                        cls_attr_name,
                        (cls_attr, event_event_subclass),
                        {
                            "__qualname__": cls_attr.__qualname__,
                            "__module__": cls_attr.__module__,
                            "__doc__": cls_attr.__doc__,
                        },
                    )
                except TypeError:
                    raise Exception(cls_attr_name, cls_attr, event_event_subclass)
                setattr(cls, cls_attr_name, event_subclass)

    return cls
