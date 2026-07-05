from copy import deepcopy
from threading import Thread
from unittest import TestCase

import eventsourcing
import eventsourcing.dcb.domain
import eventsourcing.dcb.persistence
from eventsourcing.dcb.pydantic import Decision, PydanticMapper
from tests.dcb_tests.test_persistence import DCBMapperTestCase


class MyDecision(Decision):
    a: str


class TestDecision(TestCase):
    def test_my_decision(self) -> None:
        m = MyDecision(a="a")

        d = m.as_dict()
        self.assertEqual(d, {"a": "a"})

        self.assertEqual(deepcopy(m), m)

        def f() -> None:
            self.assertEqual(deepcopy(m), m)

        t = Thread(target=f)
        t.start()
        t.join()


class TestPydanticMapper(DCBMapperTestCase):
    mapper_class = PydanticMapper

    def test_dcb_mapper(self) -> None:
        super()._test_dcb_mapper()

    def construct_decision(self) -> eventsourcing.dcb.domain.Decision:
        return MyDecision(a="1")
