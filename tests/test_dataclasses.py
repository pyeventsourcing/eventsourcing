from dataclasses import dataclass
from datetime import date, datetime
from typing import override
from uuid import UUID, uuid4

from eventsourcing.dataclasses import Decision, Transcoder
from eventsourcing.tests.persistence import (
    AggregateEventMapperTestCase,
    TaggedEventMapperTestCase,
)
from eventsourcing.timestamp import datetime_now_with_tzinfo


@dataclass
class CustomType:
    a: str
    b: UUID
    c: datetime
    d: date
    e: int
    f: tuple[int, ...]
    g: tuple[int] | None


class MyDataclassDecision(Decision):
    x: CustomType


class TestDataclassTranscoderWithTaggedEventMapper(TaggedEventMapperTestCase[Decision]):
    transcoder_class = Transcoder

    def test_tagged_event_mapper(self) -> None:
        super()._test_tagged_event_mapper()

    @override
    def construct_decision(self) -> Decision:
        return MyDataclassDecision(
            x=CustomType(
                a="1",
                b=uuid4(),
                c=datetime_now_with_tzinfo(),
                d=date(2001, 1, 2),
                e=15,
                f=(1, 2, 3),
                g=None,
            )
        )


class TestDataclassTranscoderWithAggregateEventMapper(
    AggregateEventMapperTestCase[Decision]
):
    transcoder_class = Transcoder

    def test_aggregate_event_mapper(self) -> None:
        super()._test_aggregate_event_mapper()

    @override
    def construct_decision(self) -> Decision:
        return MyDataclassDecision(
            x=CustomType(
                a="1",
                b=uuid4(),
                c=datetime_now_with_tzinfo(),
                d=date(2001, 1, 2),
                e=15,
                f=(1, 2, 3),
                g=None,
            )
        )
