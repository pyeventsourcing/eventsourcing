from functools import singledispatch, wraps
from inspect import isfunction


def applicationpolicy(arg=None):
    """
    Decorator for application policy method.

    Allows policy to be built up from methods
    registered for different event classes.
    """

    def _mutator(func):
        wrapped = singledispatch(func)

        @wraps(wrapped)
        def wrapper(*args, **kwargs):
            event = kwargs.get('event') or args[-1]
            return wrapped.dispatch(type(event))(*args, **kwargs)

        wrapper.register = wrapped.register

        return wrapper

    assert isfunction(arg), arg
    return _mutator(arg)
