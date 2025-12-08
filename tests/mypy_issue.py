# ruff: noqa: E501

# Just wanted to document that mypy (and not pyright) reports errors with the first
# case but not the second, with two constraints rather than a union bound. Not sure
# if there's something I don't understand... probably there is. Anyway, I switched to
# using a union in the code, and that does what I wanted.

from typing import Generic, Protocol, TypeVar
from uuid import UUID

# Case 1.

T_co = TypeVar("T_co", UUID, str, covariant=True)
T = TypeVar("T", UUID, str)


class P(Protocol[T_co]):
    @property
    def id(self) -> T_co:
        raise NotImplementedError


class A(Generic[T]):
    def get_items(self) -> list[P[T]]:
        return []

    def process_items(self, items: P[T]) -> None:
        pass


class B(A[T]):
    def get_items(self) -> list[P[T]]:
        # error: Incompatible return value type (got "list[P[T]]", expected "list[P[UUID]]")  [return-value]
        # error: Incompatible return value type (got "list[P[T]]", expected "list[P[str]]")  [return-value]
        return super().get_items()  # type: ignore[return-value]

    def process_items(self, items: P[T]) -> None:
        # error: Argument 1 to "process_items" of "A" has incompatible type "P[UUID]"; expected "P[T]"  [arg-type]
        # error: Argument 1 to "process_items" of "A" has incompatible type "P[str]"; expected "P[T]"  [arg-type]
        super().process_items(items)  # type: ignore[arg-type]


# Case 2.

S_co = TypeVar("S_co", bound=UUID | str, covariant=True)
S = TypeVar("S", bound=UUID | str)


class Q(Protocol[S_co]):
    @property
    def id(self) -> S_co:
        raise NotImplementedError


class C(Generic[S]):
    def get_items(self) -> list[Q[S]]:
        return []

    def process_items(self, items: Q[S]) -> None:
        pass


class D(C[S]):
    def get_items(self) -> list[Q[S]]:
        return super().get_items()

    def process_items(self, items: Q[S]) -> None:
        super().process_items(items)
