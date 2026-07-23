from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from eventsourcing import dataclasses, msgspec, pydantic
from eventsourcing.domain import AggregateEvent
from eventsourcing.persistence import AggregateEventMapper

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


@pytest.mark.benchmark(group="mapper-encode")
def test_encode_with_dataclasstranscoder(benchmark: BenchmarkFixture) -> None:
    class MyObj(dataclasses.Decision):
        a: int
        b: str
        c: float
        d: Decimal

    obj = AggregateEvent(
        originator_id=str(uuid4()),
        originator_version=1,
        decision=MyObj(
            a=1,
            b="abc" * 10,
            c=0.12345,
            d=Decimal("0.12345"),
        ),
    )

    transcoder = dataclasses.Transcoder()
    mapper = AggregateEventMapper[dataclasses.Decision](transcoder=transcoder)

    def func() -> None:
        mapper.to_stored_event(obj)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-decode")
def test_decode_with_jsontranscoder(benchmark: BenchmarkFixture) -> None:
    class MyObj(dataclasses.Decision):
        a: int
        b: str
        c: float
        d: Decimal

    obj = AggregateEvent(
        originator_id=str(uuid4()),
        originator_version=1,
        decision=MyObj(
            a=1,
            b="abc" * 10,
            c=0.12345,
            d=Decimal("0.12345"),
        ),
    )

    transcoder = dataclasses.Transcoder()
    mapper = AggregateEventMapper[dataclasses.Decision](transcoder=transcoder)

    stored_event = mapper.to_stored_event(obj)

    def func() -> None:
        mapper.to_domain_event(stored_event)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-encode")
def test_encode_with_pydantic(benchmark: BenchmarkFixture) -> None:
    class MyObj(pydantic.Decision):
        a: int
        b: str
        c: float
        d: Decimal

    obj = AggregateEvent(
        originator_id=str(uuid4()),
        originator_version=1,
        decision=MyObj(
            a=1,
            b="abc" * 10,
            c=0.12345,
            d=Decimal("0.12345"),
        ),
    )

    mapper = AggregateEventMapper[pydantic.Decision](transcoder=pydantic.Transcoder())

    def func() -> None:
        mapper.to_stored_event(obj)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-decode")
def test_decode_with_pydantic(benchmark: BenchmarkFixture) -> None:
    class MyObj(pydantic.Decision):
        a: int
        b: str
        c: float
        d: Decimal

    obj = AggregateEvent(
        originator_id=str(uuid4()),
        originator_version=1,
        decision=MyObj(
            a=1,
            b="abc" * 10,
            c=0.12345,
            d=Decimal("0.12345"),
        ),
    )

    mapper = AggregateEventMapper[pydantic.Decision](transcoder=pydantic.Transcoder())

    stored_event = mapper.to_stored_event(obj)

    def func() -> None:
        mapper.to_domain_event(stored_event)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-encode")
def test_encode_with_msgspec(benchmark: BenchmarkFixture) -> None:
    class MyObj(msgspec.Decision):
        a: int
        b: str
        c: float
        d: Decimal

    obj = AggregateEvent(
        originator_id=str(uuid4()),
        originator_version=1,
        decision=MyObj(
            a=1,
            b="abc" * 10,
            c=0.12345,
            d=Decimal("0.12345"),
        ),
    )

    mapper = AggregateEventMapper[msgspec.Decision](transcoder=msgspec.Transcoder())

    def func() -> None:
        mapper.to_stored_event(obj)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-decode")
def test_decode_with_msgspec(benchmark: BenchmarkFixture) -> None:
    class MyObj(msgspec.Decision):
        a: int
        b: str
        c: float
        d: Decimal

    obj = AggregateEvent(
        originator_id=str(uuid4()),
        originator_version=1,
        decision=MyObj(
            a=1,
            b="abc" * 10,
            c=0.12345,
            d=Decimal("0.12345"),
        ),
    )

    mapper = AggregateEventMapper[msgspec.Decision](transcoder=msgspec.Transcoder())

    stored_event = mapper.to_stored_event(obj)

    def func() -> None:
        mapper.to_domain_event(stored_event)

    benchmark(func)
