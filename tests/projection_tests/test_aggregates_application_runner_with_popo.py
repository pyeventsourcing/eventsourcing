from __future__ import annotations

from typing import ClassVar

from eventsourcing.tests.projection import AggregatesApplicationRunnerTestCase


class TestAggregatesApplicationRunnerWithPOPO(AggregatesApplicationRunnerTestCase):
    env: ClassVar[dict[str, str]] = {
        "PERSISTENCE_MODULE": "eventsourcing.popo",
    }


del AggregatesApplicationRunnerTestCase
