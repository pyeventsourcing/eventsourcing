from __future__ import annotations

import sys
from typing import TYPE_CHECKING, ClassVar, override
from unittest import skipIf

from eventsourcing.msgspec.transcoder import Transcoder
from eventsourcing.persistence import AggregateEventMapper
from eventsourcing.popo import POPOTrackingRecorder
from eventsourcing.tests.projection import (
    AggregateEventProjectionTestCase,
    StudentAnalyticsView,
    StudentAnalyticsViewTestCase,
    TaggedEventProjectionTestCase,
)
from eventsourcing.utils import get_topic

if TYPE_CHECKING:
    from eventsourcing.persistence import Tracking


class POPOStudentAnalyticsView(POPOTrackingRecorder, StudentAnalyticsView):
    def __init__(self) -> None:
        super().__init__()
        self._created_event_counter = 0
        self._subsequent_event_counter = 0

    @override
    def get_student_registered_counter(self) -> int:
        return self._created_event_counter

    @override
    def get_student_name_changed_counter(self) -> int:
        return self._subsequent_event_counter

    @override
    def incr_student_registered_counter(self, tracking: Tracking) -> None:
        with self._database_lock:
            self._assert_tracking_uniqueness(tracking)
            self._insert_tracking(tracking)
            self._created_event_counter += 1

    @override
    def incr_student_name_changed_counter(self, tracking: Tracking) -> None:
        with self._database_lock:
            self._assert_tracking_uniqueness(tracking)
            self._insert_tracking(tracking)
            self._subsequent_event_counter += 1


class TestPOPOStudentAnalytics(StudentAnalyticsViewTestCase):
    @override
    def construct_event_counters_view(self) -> StudentAnalyticsView:
        return POPOStudentAnalyticsView()


class TestAggregateEventProjectionWithPOPO(
    AggregateEventProjectionTestCase[POPOStudentAnalyticsView]
):
    env: ClassVar[dict[str, str]] = {
        "MAPPER_TOPIC": get_topic(AggregateEventMapper),
        "TRANSCODER_TOPIC": get_topic(Transcoder),
    }
    view_class = POPOStudentAnalyticsView


# TODO: Figure out actually what is causing segmentation violations with Python3.13.
#  - is happening in this test when whole test suite is run, but not when run alone
#  - was happening when run alone when DcbSpannerThrown has no attributes
#  - maybe something to do with deepcopy() in InMemoryRecorder?
@skipIf(sys.version_info[0:2] == (3, 13), "Weird occasional segmentation violation")
class TestTaggedEventCountersProjectionWithPOPO(TaggedEventProjectionTestCase):

    env: ClassVar[dict[str, str]] = {
        # "MAPPER_TOPIC": get_topic(TaggedEventMapper),
        # "TRANSCODER_TOPIC": get_topic(Transcoder),
    }
    view_class: type[StudentAnalyticsView] = POPOStudentAnalyticsView


del TaggedEventProjectionTestCase
del AggregateEventProjectionTestCase
del StudentAnalyticsViewTestCase
