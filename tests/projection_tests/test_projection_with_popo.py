from __future__ import annotations

import sys
from typing import TYPE_CHECKING, ClassVar
from unittest import skipIf

from eventsourcing.dcb.msgpack import MessagePackMapper
from eventsourcing.popo import POPOTrackingRecorder
from eventsourcing.tests.projection import (
    AggregateEventCountersProjectionTestCase,
    EventCountersView,
    EventCountersViewTestCase,
    TaggedDecisionCountersProjectionTestCase,
)
from eventsourcing.utils import get_topic

if TYPE_CHECKING:
    from eventsourcing.persistence import Tracking


class POPOEventCounters(POPOTrackingRecorder, EventCountersView):
    def __init__(self) -> None:
        super().__init__()
        self._created_event_counter = 0
        self._subsequent_event_counter = 0

    def get_created_event_counter(self) -> int:
        return self._created_event_counter

    def get_subsequent_event_counter(self) -> int:
        return self._subsequent_event_counter

    def incr_created_event_counter(self, tracking: Tracking) -> None:
        with self._database_lock:
            self._assert_tracking_uniqueness(tracking)
            self._insert_tracking(tracking)
            self._created_event_counter += 1

    def incr_subsequent_event_counter(self, tracking: Tracking) -> None:
        with self._database_lock:
            self._assert_tracking_uniqueness(tracking)
            self._insert_tracking(tracking)
            self._subsequent_event_counter += 1


class TestPOPOEventCounters(EventCountersViewTestCase):
    def construct_event_counters_view(self) -> EventCountersView:
        return POPOEventCounters()


class TestAggregateEventCountersProjectionWithPOPO(
    AggregateEventCountersProjectionTestCase
):
    view_class: type[EventCountersView] = POPOEventCounters


# TODO: Figure out actually what is causing segmentation violations with Python3.13.
#  - is happening in this test when whole test suite is run, but not when run alone
#  - was happening when run alone when DCBSpannerThrown has no attributes
#  - maybe something to do with deepcopy() in InMemoryRecorder?
@skipIf(sys.version_info[0:2] == (3, 13), "Weird occasional segmentation violation")
class TestTaggedDecisionCountersProjectionWithPOPO(
    TaggedDecisionCountersProjectionTestCase
):

    env: ClassVar[dict[str, str]] = {"MAPPER_TOPIC": get_topic(MessagePackMapper)}
    view_class: type[EventCountersView] = POPOEventCounters


del TaggedDecisionCountersProjectionTestCase
del AggregateEventCountersProjectionTestCase
del EventCountersViewTestCase
