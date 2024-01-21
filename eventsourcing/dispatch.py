from __future__ import annotations

import sys

if sys.version_info >= (3, 8):  # pragma: no cover
    from functools import singledispatchmethod as _singledispatchmethod

    class singledispatchmethod(_singledispatchmethod):
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
                # Todo: Fix this....
                return method or cls

        def __get__(self, obj, cls=None):
            for registered_cls, registered_method in self.deferred_registrations:
                self.dispatcher.register(registered_cls, func=registered_method)
            self.deferred_registrations = []
            return super().__get__(obj, cls=cls)

else:
    from functools import singledispatch, update_wrapper

    class singledispatchmethod:
        """Single-dispatch generic method descriptor.

        Supports wrapping existing descriptors and handles non-descriptor
        callables as instance methods.
        """

        def __init__(self, func):
            if not callable(func) and not hasattr(func, "__get__"):
                raise TypeError(f"{func!r} is not callable or a descriptor")

            self.dispatcher = singledispatch(func)
            self.func = func
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
                cls.__wrapped__ = cls.__func__  # for globals in typing.get_type_hints()
            try:
                return self.dispatcher.register(cls, func=method)
            except NameError as e:
                self.deferred_registrations.append([cls, method, e])
                # Todo: Fix this....
                return method or cls

        def __get__(self, obj, cls=None):
            for cls, method, original_e in self.deferred_registrations:
                try:
                    self.dispatcher.register(cls, func=method)
                except NameError as e:
                    raise original_e from e
            self.deferred_registrations = []

            def _method(*args, **kwargs):
                method = self.dispatcher.dispatch(args[0].__class__)
                return method.__get__(obj, cls)(*args, **kwargs)

            _method.__isabstractmethod__ = self.__isabstractmethod__
            _method.register = self.register
            update_wrapper(_method, self.func)
            return _method

        @property
        def __isabstractmethod__(self):
            return getattr(self.func, "__isabstractmethod__", False)
