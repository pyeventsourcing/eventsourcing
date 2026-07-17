from copy import deepcopy
from threading import Thread
from unittest import TestCase

import eventsourcing.domain_new
from eventsourcing.msgspec.immutable import MsgspecDecision
from eventsourcing.msgspec.transcoder import MsgspecTranscoder
from eventsourcing.tests.persistence import (
    AggregateEventMapperTestCase,
    TaggedEventMapperTestCase,
)


class MyMsgspecDecision(MsgspecDecision):
    a: str


class TestDecision(TestCase):
    def test_my_decision(self) -> None:
        # Trying to isolate segmentation violation in Python3.13 with
        # projection using DCB application with ImMemoryDCBRecorder and
        # eventsourcing.dcb.msgspec.Decision. One suspect is deepcopy of
        # msgspec.Struct subclasses, perhaps when crossing threads. This
        # test tries to replicate what InMemoryDCBRecorder does with a
        # subscription (deepcopy on a different thread). However, no segv.
        m = MyMsgspecDecision(a="a")
        self.assertEqual(deepcopy(m), m)

        def f() -> None:
            self.assertEqual(deepcopy(m), m)

        t = Thread(target=f)
        t.start()
        t.join()


class TestTaggedEventMapperWithMsgspecTranscoder(TaggedEventMapperTestCase):
    transcoder_class = MsgspecTranscoder

    def test_tagged_event_mapper(self) -> None:
        super()._test_tagged_event_mapper()

    def construct_decision(self) -> eventsourcing.domain_new.AbstractDecision:
        return MyMsgspecDecision(a="1")


class TestMsgspecTranscoderWithAggregateEventMapper(AggregateEventMapperTestCase):
    transcoder_class = MsgspecTranscoder

    def test_aggregate_event_mapper(self) -> None:
        super()._test_aggregate_event_mapper()

    def construct_decision(self) -> eventsourcing.domain_new.AbstractDecision:
        return MyMsgspecDecision(a="1")
