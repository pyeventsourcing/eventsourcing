from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

import eventsourcing.dataclasses.immutable
import eventsourcing.domain_old
import eventsourcing.msgspec.immutable
import eventsourcing.pydantic.immutable
from eventsourcing.dataclasses.transcoder import DataclassTranscoder
from eventsourcing.domain_new import AggregateEvent
from eventsourcing.msgspec.transcoder import MsgspecTranscoder
from eventsourcing.persistence import AggregateEventMapper
from eventsourcing.pydantic.transcoder import PydanticTranscoder

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


@pytest.mark.benchmark(group="mapper-encode")
def test_encode_with_dataclasstranscoder(benchmark: BenchmarkFixture) -> None:
    @dataclass(frozen=True, kw_only=True)
    class MyObj(eventsourcing.dataclasses.immutable.DataclassDecision):
        a: int
        b: str
        c: float
        d: Decimal

    obj = AggregateEvent(
        originator_id=uuid4(),
        originator_version=1,
        decision=MyObj(
            a=1,
            b="abc" * 10,
            c=0.12345,
            d=Decimal("0.12345"),
        ),
    )

    transcoder = DataclassTranscoder()
    mapper = AggregateEventMapper(transcoder=transcoder)

    def func() -> None:
        mapper.to_stored_event(obj)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-decode")
def test_decode_with_jsontranscoder(benchmark: BenchmarkFixture) -> None:
    @dataclass(frozen=True, kw_only=True)
    class MyObj(eventsourcing.dataclasses.immutable.DataclassDecision):
        a: int
        b: str
        c: float
        d: Decimal

    obj = AggregateEvent(
        originator_id=uuid4(),
        originator_version=1,
        decision=MyObj(
            a=1,
            b="abc" * 10,
            c=0.12345,
            d=Decimal("0.12345"),
        ),
    )

    transcoder = DataclassTranscoder()
    mapper = AggregateEventMapper(transcoder=transcoder)

    stored_event = mapper.to_stored_event(obj)

    def func() -> None:
        mapper.to_domain_event(stored_event)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-encode")
def test_encode_with_pydantic(benchmark: BenchmarkFixture) -> None:
    class MyObj(eventsourcing.pydantic.immutable.PydanticDecision):
        a: int
        b: str
        c: float
        d: Decimal

    obj = AggregateEvent(
        originator_id=uuid4(),
        originator_version=1,
        decision=MyObj(
            a=1,
            b="abc" * 10,
            c=0.12345,
            d=Decimal("0.12345"),
        ),
    )

    mapper = AggregateEventMapper(transcoder=PydanticTranscoder)

    def func() -> None:
        mapper.to_stored_event(obj)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-decode")
def test_decode_with_pydantic(benchmark: BenchmarkFixture) -> None:
    class MyObj(eventsourcing.pydantic.immutable.PydanticDecision):
        a: int
        b: str
        c: float
        d: Decimal

    obj = AggregateEvent(
        originator_id=uuid4(),
        originator_version=1,
        decision=MyObj(
            a=1,
            b="abc" * 10,
            c=0.12345,
            d=Decimal("0.12345"),
        ),
    )

    mapper = AggregateEventMapper(transcoder=PydanticTranscoder)

    stored_event = mapper.to_stored_event(obj)

    def func() -> None:
        mapper.to_domain_event(stored_event)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-encode")
def test_encode_with_msgspec(benchmark: BenchmarkFixture) -> None:
    class MyObj(eventsourcing.msgspec.immutable.MsgspecDecision):
        a: int
        b: str
        c: float
        d: Decimal

    obj = AggregateEvent(
        originator_id=uuid4(),
        originator_version=1,
        decision=MyObj(
            a=1,
            b="abc" * 10,
            c=0.12345,
            d=Decimal("0.12345"),
        ),
    )

    mapper = AggregateEventMapper(transcoder=MsgspecTranscoder)

    def func() -> None:
        mapper.to_stored_event(obj)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-decode")
def test_decode_with_msgspec(benchmark: BenchmarkFixture) -> None:
    class MyObj(eventsourcing.msgspec.immutable.MsgspecDecision):
        a: int
        b: str
        c: float
        d: Decimal

    obj = AggregateEvent(
        originator_id=uuid4(),
        originator_version=1,
        decision=MyObj(
            a=1,
            b="abc" * 10,
            c=0.12345,
            d=Decimal("0.12345"),
        ),
    )

    mapper = AggregateEventMapper(transcoder=MsgspecTranscoder)

    stored_event = mapper.to_stored_event(obj)

    def func() -> None:
        mapper.to_domain_event(stored_event)

    benchmark(func)
