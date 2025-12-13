from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

import eventsourcing.domain
import examples.aggregate7.immutablemodel
import examples.aggregate9.immutablemodel
from eventsourcing.domain import datetime_now_with_tzinfo
from eventsourcing.persistence import (
    DatetimeAsISO,
    DecimalAsStr,
    JSONTranscoder,
    Mapper,
    UUIDAsHex,
)
from examples.aggregate7.orjsonpydantic import OrjsonTranscoder, PydanticMapper
from examples.aggregate9.msgpack import MessagePackMapper, NullTranscoder

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


@pytest.mark.benchmark(group="mapper-encode")
def test_encode_with_jsontranscoder(benchmark: BenchmarkFixture) -> None:
    @dataclass(frozen=True)
    class MyObj(eventsourcing.domain.DomainEvent):
        a: int
        b: str
        c: float
        d: Decimal

    obj = MyObj(
        originator_id=uuid4(),
        originator_version=1,
        timestamp=datetime_now_with_tzinfo(),
        a=1,
        b="abc" * 10,
        c=0.12345,
        d=Decimal("0.12345"),
    )

    transcoder = JSONTranscoder()
    transcoder.register(UUIDAsHex())
    transcoder.register(DatetimeAsISO())
    transcoder.register(DecimalAsStr())
    mapper = Mapper[UUID](transcoder=transcoder)

    def func() -> None:
        mapper.to_stored_event(obj)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-decode")
def test_decode_with_jsontranscoder(benchmark: BenchmarkFixture) -> None:
    @dataclass(frozen=True)
    class MyObj(eventsourcing.domain.DomainEvent):
        a: int
        b: str
        c: float
        d: Decimal

    obj = MyObj(
        originator_id=uuid4(),
        originator_version=1,
        timestamp=datetime_now_with_tzinfo(),
        a=1,
        b="abc" * 10,
        c=0.12345,
        d=Decimal("0.12345"),
    )

    transcoder = JSONTranscoder()
    transcoder.register(UUIDAsHex())
    transcoder.register(DatetimeAsISO())
    transcoder.register(DecimalAsStr())
    mapper = Mapper[UUID](transcoder=transcoder)

    stored_event = mapper.to_stored_event(obj)

    def func() -> None:
        mapper.to_domain_event(stored_event)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-encode")
def test_encode_with_orjsonpydantic(benchmark: BenchmarkFixture) -> None:
    class MyObj(examples.aggregate7.immutablemodel.DomainEvent):
        a: int
        b: str
        c: float
        d: Decimal

    obj = MyObj(
        originator_id=uuid4(),
        originator_version=1,
        timestamp=datetime_now_with_tzinfo(),
        a=1,
        b="abc" * 10,
        c=0.12345,
        d=Decimal("0.12345"),
    )

    transcoder = OrjsonTranscoder()
    mapper = PydanticMapper(transcoder=transcoder)

    def func() -> None:
        mapper.to_stored_event(obj)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-decode")
def test_decode_with_orjsonpydantic(benchmark: BenchmarkFixture) -> None:
    class MyObj(examples.aggregate7.immutablemodel.DomainEvent):
        a: int
        b: str
        c: float
        d: Decimal

    obj = MyObj(
        originator_id=uuid4(),
        originator_version=1,
        timestamp=datetime_now_with_tzinfo(),
        a=1,
        b="abc" * 10,
        c=0.12345,
        d=Decimal("0.12345"),
    )

    transcoder = OrjsonTranscoder()
    mapper = PydanticMapper(transcoder=transcoder)

    stored_event = mapper.to_stored_event(obj)

    def func() -> None:
        mapper.to_domain_event(stored_event)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-encode")
def test_encode_with_msgspec(benchmark: BenchmarkFixture) -> None:
    class MyObj(examples.aggregate9.immutablemodel.DomainEvent, frozen=True):
        a: int
        b: str
        c: float
        d: Decimal

    obj = MyObj(
        originator_id=uuid4(),
        originator_version=1,
        timestamp=datetime_now_with_tzinfo(),
        a=1,
        b="abc" * 10,
        c=0.12345,
        d=Decimal("0.12345"),
    )

    mapper = MessagePackMapper(transcoder=NullTranscoder())

    def func() -> None:
        mapper.to_stored_event(obj)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-decode")
def test_decode_with_msgspec(benchmark: BenchmarkFixture) -> None:
    class MyObj(examples.aggregate9.immutablemodel.DomainEvent, frozen=True):
        a: int
        b: str
        c: float
        d: Decimal

    obj = MyObj(
        originator_id=uuid4(),
        originator_version=1,
        timestamp=datetime_now_with_tzinfo(),
        a=1,
        b="abc" * 10,
        c=0.12345,
        d=Decimal("0.12345"),
    )

    mapper = MessagePackMapper(transcoder=NullTranscoder())

    stored_event = mapper.to_stored_event(obj)

    def func() -> None:
        mapper.to_domain_event(stored_event)

    benchmark(func)
