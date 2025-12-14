from copy import deepcopy
from threading import Thread
from unittest import TestCase

from eventsourcing.dcb.msgpack import Decision


class MyDecision(Decision):
    a: str


class Test(TestCase):
    def test(self) -> None:
        # Trying to isolate segmentation violation in Python3.13 with
        # projection using DCB application with ImMemoryDCBRecorder and
        # eventsourcing.dcb.msgpack.Decision. One suspect is deepcopy of
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
