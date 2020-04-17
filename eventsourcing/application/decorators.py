from functools import _find_impl, singledispatch, wraps
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
                return cache[event_type]
            except KeyError:
                handler = _find_impl(event_type, handlers) or func
                cache[event_type] = handler
                return handler

        @wraps(func)
        def policy_function_wrapper(*args, **kwargs):
            event = kwargs.get("event") or args[-1]
            return dispatch(type(event))(*args, **kwargs)

        def register(event_type):
            def registered_function_decorator(func):
                handlers[event_type] = func
                return func

            return registered_function_decorator

        policy_function_wrapper.register = register

        return policy_function_wrapper

    return _mutator(arg)
