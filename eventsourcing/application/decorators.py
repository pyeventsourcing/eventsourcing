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
