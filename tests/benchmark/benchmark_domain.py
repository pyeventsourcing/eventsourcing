from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from eventsourcing.domain import event
from eventsourcing.pydantic.immutable import PydanticDecision
from eventsourcing.pydantic.mutable import PydanticAggregate

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


@pytest.mark.benchmark(group="define-aggregate-subclass")
def test_define_aggregate(benchmark: BenchmarkFixture) -> None:
    def define_aggregate() -> None:
        class A(PydanticAggregate):
            @event("Created")
            def __init__(self, a: int, b: int):
                self.a = a
                self.b = b

            @event("Continued")
            def subsequent(self, a: int, b: int) -> None:
                self.a = a
                self.b = b

    benchmark(define_aggregate)


@pytest.mark.benchmark(group="construct-aggregate-subclass")
def test_construct_aggregate_subclass(benchmark: BenchmarkFixture) -> None:
    class A(PydanticAggregate):
        @event("Created")
        def __init__(self, a: int, b: int):
            self.a = a
            self.b = b

        @event("Commanded")
        def command(self, a: int, b: int) -> None:
            self.a = a
            self.b = b

    def construct_custom() -> None:
        A(a=1, b=2)

    benchmark(construct_custom)


@pytest.mark.benchmark(group="trigger-aggregate-event")
def test_trigger_aggregate_event(benchmark: BenchmarkFixture) -> None:
    class A(PydanticAggregate):
        @event("Created")
        def __init__(self, a: int, b: int):
            self.a = a
            self.b = b

        class Commanded(PydanticDecision):
            a: int
            b: int

        @event(Commanded)
        def command(self, a: int, b: int) -> None:
            self.a = a
            self.b = b

    a = A(a=1, b=2)

    def func() -> None:
        a.trigger_event(A.Commanded, a=3, b=4)

    benchmark(func)


@pytest.mark.benchmark(group="call-decorated-command-method")
def test_call_decorated_command_method(benchmark: BenchmarkFixture) -> None:
    class A(PydanticAggregate):
        @event("Created")
        def __init__(self, a: int, b: int):
            self.a = a
            self.b = b

        class Commanded(PydanticDecision):
            a: int
            b: int

        @event(Commanded)
        def command(self, a: int, b: int) -> None:
            self.a = a
            self.b = b

    a = A(a=1, b=2)

    def func() -> None:
        a.command(a=3, b=4)

    benchmark(func)
