from copy import deepcopy
from threading import Thread
from unittest import TestCase

import eventsourcing.domain
from eventsourcing.msgspec.immutable import Decision
from eventsourcing.msgspec.transcoder import Transcoder
from eventsourcing.tests.persistence import (
    AggregateEventMapperTestCase,
    TaggedEventMapperTestCase,
)


class MyMsgspecDecision(Decision):
    a: str


class TestDecision(TestCase):
    def test_my_decision(self) -> None:
        # Trying to isolate segmentation violation in Python3.13 with
        # projection using DCB application with ImMemoryDcbRecorder and
        # eventsourcing.dcb.msgspec.Decision. One suspect is deepcopy of
        # msgspec.Struct subclasses, perhaps when crossing threads. This
        # test tries to replicate what InMemoryDcbRecorder does with a
        # subscription (deepcopy on a different thread). However, no segv.
        m = MyMsgspecDecision(a="a")
        self.assertEqual(deepcopy(m), m)

        def f() -> None:
            self.assertEqual(deepcopy(m), m)

        t = Thread(target=f)
        t.start()
        t.join()


class TestTaggedEventMapperWithMsgspecTranscoder(TaggedEventMapperTestCase):
    transcoder_class = Transcoder

    def test_tagged_event_mapper(self) -> None:
        super()._test_tagged_event_mapper()

    def construct_decision(self) -> eventsourcing.domain.AbstractDecision:
        return MyMsgspecDecision(a="1")


class TestMsgspecTranscoderWithAggregateEventMapper(AggregateEventMapperTestCase):
    transcoder_class = Transcoder

    def test_aggregate_event_mapper(self) -> None:
        super()._test_aggregate_event_mapper()

    def construct_decision(self) -> eventsourcing.domain.AbstractDecision:
        return MyMsgspecDecision(a="1")
