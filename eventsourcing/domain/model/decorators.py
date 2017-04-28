"""
:mod:`eventsourcing.domain.model.decorators`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from inspect import isfunction

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

    Example usage:
    
    .. code::
    
        # this example shows a custom handler that reacts to Todo.Created
        # event and saves a projection of a Todo model object
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


def mutator(func):
    """Like singledispatch, but dispatches on type of last arg,
    which fits better with reduce().
    """

    wrapped = singledispatch(func)

    def wrapper(*args, **kw):
        return wrapped.dispatch(args[-1].__class__)(*args, **kw)

    wrapper.register = wrapped.register

    return wrapper


def attribute(getter):
    """
    When used as a method decorator, returns a property object
    with the method as the getter and a setter defined to call
    instance method _change_attribute(), which publishes an
    AttributeChanged event.
    """
    if isfunction(getter):
        def setter(self, value):
            name = '_' + getter.__name__
            self._change_attribute(name=name, value=value)

        def new_getter(self):
            name = '_' + getter.__name__
            return getattr(self, name)

        return property(fget=new_getter, fset=setter)
    else:
        raise ProgrammingError("Expected a function, got: {}".format(repr(getter)))
