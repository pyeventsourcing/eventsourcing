from __future__ import annotations

from typing import ClassVar

from eventsourcing.msgspec.transcoder import MsgspecTranscoder
from eventsourcing.persistence import AggregateEventMapper
from eventsourcing.tests.projection import EventSourcedProjectionTestCase
from eventsourcing.utils import get_topic


class TestEventSourcedProjectionWithPOPO(EventSourcedProjectionTestCase):
    env: ClassVar[dict[str, str]] = {
        "PERSISTENCE_MODULE": "eventsourcing.popo",
    }


del EventSourcedProjectionTestCase
