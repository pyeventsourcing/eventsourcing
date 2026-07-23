from copy import deepcopy
from threading import Thread
from unittest import TestCase

import eventsourcing.domain
from eventsourcing.pydantic import Decision, Transcoder
from eventsourcing.tests.persistence import (
    AggregateEventMapperTestCase,
    TaggedEventMapperTestCase,
)


class MyPydanticDecision(Decision):
    a: str


class TestDecision(TestCase):
    def test_my_decision(self) -> None:
        m = MyPydanticDecision(a="a")

        d = m.as_dict()
        self.assertEqual(d, {"a": "a"})

        self.assertEqual(deepcopy(m), m)

        def f() -> None:
            self.assertEqual(deepcopy(m), m)

        t = Thread(target=f)
        t.start()
        t.join()


class TestPydanticTranscoderWithTaggedEventMapper(TaggedEventMapperTestCase):
    transcoder_class = Transcoder

    def test_tagged_event_mapper(self) -> None:
        super()._test_tagged_event_mapper()

    def construct_decision(self) -> eventsourcing.domain.AbstractDecision:
        return MyPydanticDecision(a="1")


class TestPydanticTranscoderWithAggregateEventMapper(AggregateEventMapperTestCase):
    transcoder_class = Transcoder

    def test_aggregate_event_mapper(self) -> None:
        super()._test_aggregate_event_mapper()

    def construct_decision(self) -> eventsourcing.domain.AbstractDecision:
        return MyPydanticDecision(a="1")
