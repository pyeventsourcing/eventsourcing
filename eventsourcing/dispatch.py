from __future__ import annotations

from functools import singledispatchmethod as _singledispatchmethod


class singledispatchmethod(_singledispatchmethod):  # noqa: N801
    def __init__(self, func):
        super().__init__(func)
        self.deferred_registrations = []

    def register(self, cls, method=None):
        """generic_method.register(cls, func) -> func

        Registers a new implementation for the given *cls* on a *generic_method*.
        """
        if isinstance(cls, (classmethod, staticmethod)):
            first_annotation = {}
            for k, v in cls.__func__.__annotations__.items():
                first_annotation[k] = v
                break
            cls.__annotations__ = first_annotation

            # for globals in typing.get_type_hints() in Python 3.8 and 3.9
            if not hasattr(cls, "__wrapped__"):
                cls.__wrapped__ = cls.__func__

        try:
            return self.dispatcher.register(cls, func=method)
        except NameError:
            self.deferred_registrations.append([cls, method])
            # TODO: Fix this....
            return method or cls

    def __get__(self, obj, cls=None):
        for registered_cls, registered_method in self.deferred_registrations:
            self.dispatcher.register(registered_cls, func=registered_method)
        self.deferred_registrations = []
        return super().__get__(obj, cls=cls)
