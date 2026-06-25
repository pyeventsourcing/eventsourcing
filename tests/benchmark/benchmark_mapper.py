from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

import eventsourcing.domain
import eventsourcing.msgspec.immutablemodel
import eventsourcing.pydantic.immutablemodel
from eventsourcing.msgspec.mapper import MsgspecMapper
from eventsourcing.persistence import (
    DataclassMapper,
    DatetimeAsISO,
    DecimalAsStr,
    JSONTranscoder,
    NullTranscoder,
    UUIDAsHex,
)
from eventsourcing.pydantic.mapper import PydanticMapper

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture


@pytest.mark.benchmark(group="mapper-encode")
def test_encode_with_jsontranscoder(benchmark: BenchmarkFixture) -> None:
    @dataclass(frozen=True, kw_only=True)
    class MyObj(eventsourcing.domain.DomainEvent):
        a: int
        b: str
        c: float
        d: Decimal

    obj = MyObj(
        originator_id=uuid4(),
        originator_version=1,
        a=1,
        b="abc" * 10,
        c=0.12345,
        d=Decimal("0.12345"),
    )

    transcoder = JSONTranscoder()
    transcoder.register(UUIDAsHex())
    transcoder.register(DatetimeAsISO())
    transcoder.register(DecimalAsStr())
    mapper = DataclassMapper(transcoder=transcoder)

    def func() -> None:
        mapper.to_stored_event(obj)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-decode")
def test_decode_with_jsontranscoder(benchmark: BenchmarkFixture) -> None:
    @dataclass(frozen=True, kw_only=True)
    class MyObj(eventsourcing.domain.DomainEvent):
        a: int
        b: str
        c: float
        d: Decimal

    obj = MyObj(
        originator_id=uuid4(),
        originator_version=1,
        a=1,
        b="abc" * 10,
        c=0.12345,
        d=Decimal("0.12345"),
    )

    transcoder = JSONTranscoder()
    transcoder.register(UUIDAsHex())
    transcoder.register(DatetimeAsISO())
    transcoder.register(DecimalAsStr())
    mapper = DataclassMapper(transcoder=transcoder)

    stored_event = mapper.to_stored_event(obj)

    def func() -> None:
        mapper.to_domain_event(stored_event)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-encode")
def test_encode_with_pydantic(benchmark: BenchmarkFixture) -> None:
    class MyObj(eventsourcing.pydantic.immutablemodel.DomainEvent):
        a: int
        b: str
        c: float
        d: Decimal

    obj = MyObj(
        originator_id=uuid4(),
        originator_version=1,
        a=1,
        b="abc" * 10,
        c=0.12345,
        d=Decimal("0.12345"),
    )

    mapper = PydanticMapper(transcoder=(NullTranscoder()))

    def func() -> None:
        mapper.to_stored_event(obj)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-decode")
def test_decode_with_pydantic(benchmark: BenchmarkFixture) -> None:
    class MyObj(eventsourcing.pydantic.immutablemodel.DomainEvent):
        a: int
        b: str
        c: float
        d: Decimal

    obj = MyObj(
        originator_id=uuid4(),
        originator_version=1,
        a=1,
        b="abc" * 10,
        c=0.12345,
        d=Decimal("0.12345"),
    )

    # Not actually needed
    mapper = PydanticMapper(transcoder=(NullTranscoder()))

    stored_event = mapper.to_stored_event(obj)

    def func() -> None:
        mapper.to_domain_event(stored_event)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-encode")
def test_encode_with_msgspec(benchmark: BenchmarkFixture) -> None:
    class MyObj(eventsourcing.msgspec.immutablemodel.DomainEvent):
        a: int
        b: str
        c: float
        d: Decimal

    obj = MyObj(
        originator_id=uuid4(),
        originator_version=1,
        a=1,
        b="abc" * 10,
        c=0.12345,
        d=Decimal("0.12345"),
    )

    mapper = MsgspecMapper(transcoder=NullTranscoder())

    def func() -> None:
        mapper.to_stored_event(obj)

    benchmark(func)


@pytest.mark.benchmark(group="mapper-decode")
def test_decode_with_msgspec(benchmark: BenchmarkFixture) -> None:
    class MyObj(eventsourcing.msgspec.immutablemodel.DomainEvent):
        a: int
        b: str
        c: float
        d: Decimal

    obj = MyObj(
        originator_id=uuid4(),
        originator_version=1,
        a=1,
        b="abc" * 10,
        c=0.12345,
        d=Decimal("0.12345"),
    )

    mapper = MsgspecMapper(transcoder=NullTranscoder())

    stored_event = mapper.to_stored_event(obj)

    def func() -> None:
        mapper.to_domain_event(stored_event)

    benchmark(func)
