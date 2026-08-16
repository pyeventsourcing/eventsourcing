from __future__ import annotations

import functools
import types
from collections.abc import Callable
from threading import Lock
from typing import TYPE_CHECKING, Any, cast, overload, override

if TYPE_CHECKING:

    class _singledispatchmethod[T](functools.singledispatchmethod[T]):  # noqa: N801
        pass

else:

    class _singledispatchmethod[T](functools.singledispatchmethod):  # noqa: N801
        pass


type _RegType = type[Any] | types.UnionType


class singledispatchmethod[T](_singledispatchmethod[T]):  # noqa: N801
    def __init__(self, func: Callable[..., T]) -> None:
        super().__init__(func)
        self.deferred_registrations_lock = Lock()
        self.deferred_registrations: list[Callable[..., T]] = []

    @overload
    def register(
        self, cls: _RegType, method: None = None
    ) -> Callable[[Callable[..., T]], Callable[..., T]]: ...
    @overload
    def register(
        self, cls: Callable[..., T], method: None = None
    ) -> Callable[..., T]: ...
    @overload
    def register(self, cls: _RegType, method: Callable[..., T]) -> Callable[..., T]: ...
    @override
    def register(
        self,
        cls: _RegType | Callable[..., T],
        method: Callable[..., T] | None = None,
    ) -> Callable[[Callable[..., T]], Callable[..., T]] | Callable[..., T]:
        """generic_method.register(cls, func) -> func

        Registers a new implementation for the given *cls* on a *generic_method*.
        """
        try:
            if method is None:
                return super().register(cls)
            return super().register(cast(_RegType, cls), method)
        except (NameError, TypeError):  # NameError <= Py3.13, TypeError >= Py3.14
            if isinstance(cls, (staticmethod, types.FunctionType)) and method is None:
                self.deferred_registrations.append(cast(Callable[..., T], cls))
                return cast(Callable[..., T], cls)
            raise

    @override
    def __get__[S](self, obj: S, cls: type[S] | None = None) -> Callable[..., T]:
        if self.deferred_registrations:
            with self.deferred_registrations_lock:
                for deferred_callable in self.deferred_registrations:
                    super().register(deferred_callable)
                self.deferred_registrations = []
        return super().__get__(obj, cls=cls)
