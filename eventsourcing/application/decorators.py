from functools import singledispatch, wraps
from inspect import isfunction
from typing import Callable, no_type_check


def applicationpolicy(arg: Callable) -> Callable:
    """
    Decorator for application policy method.

    Allows policy to be built up from methods
    registered for different event classes.
    """

    assert isfunction(arg), arg

    @no_type_check
    def _mutator(func):
        wrapped = singledispatch(func)

        @wraps(wrapped)
        def wrapper(*args, **kwargs):
            event = kwargs.get("event") or args[-1]
            return wrapped.dispatch(type(event))(*args, **kwargs)

        wrapper.register = wrapped.register

        return wrapper

    return _mutator(arg)


def applicationpolicy2(arg: Callable) -> Callable:
    """
    This one doesn't use weakrefs.
    """
    handlers = {}
    cache = {}

    def _mutator(func):

        def dispatch(event_type):
            try:
                return handlers[event_type]
            except KeyError:
                try:
                    return cache[event_type]
                except KeyError:
                    for key, value in handlers:
                        if issubclass(event_type, key):
                            cache[event_type] = value
                            return value
                    else:
                        cache[event_type] = func
                        return func

        def register(event_type):
            def registered(func):
                handlers[event_type] = func
            return registered

        @wraps(func)
        def wrapper(*args, **kwargs):
            event = kwargs.get("event") or args[-1]
            return dispatch(type(event))(*args, **kwargs)

        wrapper.register = register

        return wrapper

    return _mutator(arg)
