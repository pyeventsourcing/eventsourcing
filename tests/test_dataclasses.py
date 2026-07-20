from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID, uuid4

import eventsourcing.dcb.persistence
import eventsourcing.domain
from eventsourcing.dataclasses.immutable import DataclassDecision
from eventsourcing.dataclasses.transcoder import DataclassTranscoder
from eventsourcing.domain import datetime_now_with_tzinfo
from eventsourcing.tests.persistence import (
    AggregateEventMapperTestCase,
    TaggedEventMapperTestCase,
)


@dataclass
class CustomType:
    a: str
    b: UUID
    c: datetime
    d: date
    e: int
    f: tuple[int, ...]
    g: tuple[int] | None


class MyDataclassDecision(DataclassDecision):
    x: CustomType


class TestDataclassTranscoderWithTaggedEventMapper(TaggedEventMapperTestCase):
    transcoder_class = DataclassTranscoder

    def test_tagged_event_mapper(self) -> None:
        super()._test_tagged_event_mapper()

    def construct_decision(self) -> eventsourcing.domain.AbstractDecision:
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


class TestDataclassTranscoderWithAggregateEventMapper(AggregateEventMapperTestCase):
    transcoder_class = DataclassTranscoder

    def test_aggregate_event_mapper(self) -> None:
        super()._test_aggregate_event_mapper()

    def construct_decision(self) -> eventsourcing.domain.AbstractDecision:
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
