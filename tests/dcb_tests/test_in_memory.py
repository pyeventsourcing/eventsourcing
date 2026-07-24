from __future__ import annotations

from eventsourcing.dcb.popo import InMemoryDcbRecorder
from eventsourcing.dcb.tests import DcbRecorderTestCase


class TestInMemoryDcbRecorder(DcbRecorderTestCase):
    def test_append_read(self) -> None:
        self._test_append_read(InMemoryDcbRecorder())

    def test_append_subscribe(self) -> None:
        self._test_append_subscribe(InMemoryDcbRecorder())
