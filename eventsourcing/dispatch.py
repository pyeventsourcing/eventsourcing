from __future__ import annotations

import functools
import types
from collections.abc import Callable
from threading import Lock
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast, overload

_T = TypeVar("_T")
_S = TypeVar("_S")

if TYPE_CHECKING:

    class _singledispatchmethod(functools.singledispatchmethod[_T]):  # noqa: N801
        pass

else:

    class _singledispatchmethod(  # noqa: N801
        functools.singledispatchmethod, Generic[_T]
    ):
        pass


_RegType = type[Any] | types.UnionType


class singledispatchmethod(_singledispatchmethod[_T]):  # noqa: N801
    def __init__(self, func: Callable[..., _T]) -> None:
        super().__init__(func)
        self.deferred_registrations_lock = Lock()
        self.deferred_registrations: list[Callable[..., _T]] = []

    @overload
    def register(
        self, cls: _RegType, method: None = None
    ) -> Callable[[Callable[..., _T]], Callable[..., _T]]: ...
    @overload
    def register(
        self, cls: Callable[..., _T], method: None = None
    ) -> Callable[..., _T]: ...
    @overload
    def register(
        self, cls: _RegType, method: Callable[..., _T]
    ) -> Callable[..., _T]: ...
    def register(
        self,
        cls: _RegType | Callable[..., _T],
        method: Callable[..., _T] | None = None,
    ) -> Callable[[Callable[..., _T]], Callable[..., _T]] | Callable[..., _T]:
        """generic_method.register(cls, func) -> func

        Registers a new implementation for the given *cls* on a *generic_method*.
        """
        try:
            if method is None:
                return super().register(cls)
            return super().register(cast(_RegType, cls), method)
        except (NameError, TypeError):  # NameError <= Py3.13, TypeError >= Py3.14
            if isinstance(cls, (staticmethod, types.FunctionType)) and method is None:
                self.deferred_registrations.append(cast(Callable[..., _T], cls))
                return cast(Callable[..., _T], cls)
            raise

    def __get__(self, obj: _S, cls: type[_S] | None = None) -> Callable[..., _T]:
        if self.deferred_registrations:
            with self.deferred_registrations_lock:
                for deferred_callable in self.deferred_registrations:
                    super().register(deferred_callable)
                self.deferred_registrations = []
        return super().__get__(obj, cls=cls)
