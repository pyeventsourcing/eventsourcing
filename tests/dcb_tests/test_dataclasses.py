from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

import eventsourcing
import eventsourcing.dcb.domain
import eventsourcing.dcb.persistence
from eventsourcing.dcb.dataclasses import DataclassMapper, Decision
from eventsourcing.domain import datetime_now_with_tzinfo
from tests.dcb_tests.test_persistence import DCBMapperTestCase


@dataclass
class CustomType:
    a: str
    b: UUID
    c: datetime
    d: date
    e: int
    f: tuple[int, ...]
    g: tuple[int] | None


@dataclass
class MyDecision(Decision):
    x: CustomType


class TestDataclassMapper(DCBMapperTestCase):
    mapper_class = DataclassMapper[Any]

    def test_dcb_mapper(self) -> None:
        super()._test_dcb_mapper()

    def construct_decision(self) -> eventsourcing.dcb.domain.Decision:
        return MyDecision(
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
