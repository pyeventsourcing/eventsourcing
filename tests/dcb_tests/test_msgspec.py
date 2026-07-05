from copy import deepcopy
from threading import Thread
from unittest import TestCase

import eventsourcing.dcb.domain
import eventsourcing.dcb.persistence
from eventsourcing.dcb.msgspec import Decision, MsgspecMapper
from tests.dcb_tests.test_persistence import DCBMapperTestCase


class MyDecision(Decision):
    a: str


class TestDecision(TestCase):
    def test_my_decision(self) -> None:
        # Trying to isolate segmentation violation in Python3.13 with
        # projection using DCB application with ImMemoryDCBRecorder and
        # eventsourcing.dcb.msgspec.Decision. One suspect is deepcopy of
        # msgspec.Struct subclasses, perhaps when crossing threads. This
        # test tries to replicate what InMemoryDCBRecorder does with a
        # subscription (deepcopy on a different thread). However, no segv.
        m = MyDecision(a="a")
        self.assertEqual(deepcopy(m), m)

        def f() -> None:
            self.assertEqual(deepcopy(m), m)

        t = Thread(target=f)
        t.start()
        t.join()


class TestMsgpackMapper(DCBMapperTestCase):
    mapper_class = MsgspecMapper

    def test_dcb_mapper(self) -> None:
        super()._test_dcb_mapper()

    def construct_decision(self) -> eventsourcing.dcb.domain.Decision:
        return MyDecision(a="1")
