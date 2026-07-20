from __future__ import annotations

from typing import ClassVar

from eventsourcing.tests.projection import EventSourcedProjectionTestCase


class TestEventSourcedProjectionWithPOPO(EventSourcedProjectionTestCase):
    env: ClassVar[dict[str, str]] = {
        "PERSISTENCE_MODULE": "eventsourcing.popo",
    }


del EventSourcedProjectionTestCase
