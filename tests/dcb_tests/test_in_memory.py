from __future__ import annotations

from eventsourcing.dcb.popo import InMemoryDCBRecorder
from eventsourcing.dcb.tests import DCBRecorderTestCase


class TestInMemoryDCBRecorder(DCBRecorderTestCase):
    def test_append_read(self) -> None:
        self._test_append_read(InMemoryDCBRecorder())

    def test_append_subscribe(self) -> None:
        self._test_append_subscribe(InMemoryDCBRecorder())
