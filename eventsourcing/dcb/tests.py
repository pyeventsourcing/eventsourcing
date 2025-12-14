from __future__ import annotations

import json
import threading
from unittest import TestCase
from uuid import uuid4

from eventsourcing.dcb.api import (
    DCBAppendCondition,
    DCBEvent,
    DCBQuery,
    DCBQueryItem,
    DCBRecorder,
    DCBSequencedEvent,
    DCBSubscription,
    TDCBRecorder_co,
)
from eventsourcing.persistence import IntegrityError


class DCBRecorderTestCase(TestCase):

    def _test_append_read(
        self, recorder: DCBRecorder, initial_position: int = 0
    ) -> None:
        # Read all, expect no results.
        read_response = recorder.read()
        result = list(read_response)
        self.assertEqual(initial_position, len(list(result)))
        self.assertEqual(initial_position, read_response.head or 0)

        # Append one event.
        event1 = DCBEvent(type="type1", data=b"data1", tags=["tagX"])
        position = recorder.append(events=[event1])

        # Check the returned position is 1.
        self.assertEqual(1 + initial_position, position)

        # Read all, expect one event.
        read_response = recorder.read(after=initial_position)
        result = list(read_response)
        self.assertEqual(1, len(result))
        self.assertEqual(event1.data, result[0].event.data)
        self.assertEqual(1 + initial_position, read_response.head)

        # Read all after 1, expect no events.
        read_response = recorder.read(after=1 + initial_position)
        result = list(read_response)
        self.assertEqual(0, len(result))
        self.assertEqual(1 + initial_position, read_response.head)

        # Read all limit 1, expect one event.
        read_response = recorder.read(after=initial_position, limit=1)
        result = list(read_response)
        self.assertEqual(1, len(result))
        self.assertEqual(event1.data, result[0].event.data)
        self.assertEqual(1 + initial_position, read_response.head)

        # Read all limit 0, expect no events (and read_response.head is None).
        read_response = recorder.read(limit=0)
        result = list(read_response)
        self.assertEqual(0, len(result))
        self.assertEqual(None, read_response.head)

        # Read events with type1, expect 1 event.
        query_type1 = DCBQuery(items=[DCBQueryItem(types=["type1"])])
        read_response = recorder.read(query_type1, after=initial_position)
        result = list(read_response)
        self.assertEqual(1, len(result))
        self.assertEqual(event1.data, result[0].event.data)
        self.assertEqual(1 + initial_position, read_response.head)

        # Read events with type2, expect no events.
        query_type2 = DCBQuery(items=[DCBQueryItem(types=["type2"])])
        read_response = recorder.read(query_type2, after=initial_position)
        result = list(read_response)
        self.assertEqual(0, len(result))
        self.assertEqual(1 + initial_position, read_response.head)

        # Read events with tagX, expect one event.
        query_tag_x = DCBQuery(items=[DCBQueryItem(tags=["tagX"])])
        read_response = recorder.read(query_tag_x, after=initial_position)
        result = list(read_response)
        self.assertEqual(1, len(result))
        self.assertEqual(event1.data, result[0].event.data)
        self.assertEqual(1 + initial_position, read_response.head)

        # Read events with tagY, expect no events.
        query_tag_y = DCBQuery(items=[DCBQueryItem(tags=["tagY"])])
        read_response = recorder.read(query=query_tag_y, after=initial_position)
        result = list(read_response)
        self.assertEqual(0, len(result), result)
        self.assertEqual(1 + initial_position, read_response.head)

        # Read events with type1 and tagX, expect one event.
        query_type1_tag_x = DCBQuery(
            items=[DCBQueryItem(types=["type1"], tags=["tagX"])]
        )
        read_response = recorder.read(query_type1_tag_x, after=initial_position)
        result = list(read_response)
        self.assertEqual(1, len(result))
        self.assertEqual(1 + initial_position, read_response.head)

        # Read events with type1 and tagY, expect no events.
        query_type1_tag_y = DCBQuery(
            items=[DCBQueryItem(types=["type1"], tags=["tagY"])]
        )
        read_response = recorder.read(query_type1_tag_y, after=initial_position)
        result = list(read_response)
        self.assertEqual(0, len(result))
        self.assertEqual(1 + initial_position, read_response.head)

        # Read events with type2 and tagX, expect no events.
        query_type2_tag_x = DCBQuery(
            items=[DCBQueryItem(types=["type2"], tags=["tagX"])]
        )
        read_response = recorder.read(query_type2_tag_x, after=initial_position)
        result = list(read_response)
        self.assertEqual(0, len(result))
        self.assertEqual(1 + initial_position, read_response.head)

        # Append two more events.
        event2 = DCBEvent(type="type2", data=b"data2", tags=["tagA", "tagB"])
        event3 = DCBEvent(type="type3", data=b"data3", tags=["tagA", "tagC"])
        position = recorder.append(events=[event2, event3])

        # Check the returned position is 3
        self.assertEqual(3 + initial_position, position)

        # Read all, expect 3 events (in ascending order).
        read_response = recorder.read(after=initial_position)
        result = list(read_response)
        self.assertEqual(3, len(result))
        self.assertEqual(event1.data, result[0].event.data)
        self.assertEqual(event2.data, result[1].event.data)
        self.assertEqual(event3.data, result[2].event.data)
        self.assertEqual(3 + initial_position, read_response.head)

        # Read all after 1, expect two events.
        read_response = recorder.read(after=1 + initial_position)
        result = list(read_response)
        self.assertEqual(2, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(event3.data, result[1].event.data)
        self.assertEqual(3 + initial_position, read_response.head)

        # Read all after 2, expect one event.
        read_response = recorder.read(after=2 + initial_position)
        result = list(read_response)
        self.assertEqual(1, len(result))
        self.assertEqual(event3.data, result[0].event.data)
        self.assertEqual(3 + initial_position, read_response.head)

        # Read all after 1, limit 1, expect one event.
        read_response = recorder.read(after=1 + initial_position, limit=1)
        result = list(read_response)
        self.assertEqual(1, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(2 + initial_position, read_response.head)

        # Read type1 after 1, expect no events.
        read_response = recorder.read(query_type1, after=1 + initial_position)
        result = list(read_response)
        self.assertEqual(0, len(result))
        self.assertEqual(3 + initial_position, read_response.head)

        # Read tagX after 1, expect no events.
        read_response = recorder.read(query_tag_x, after=1 + initial_position)
        result = list(read_response)
        self.assertEqual(0, len(result))
        self.assertEqual(3 + initial_position, read_response.head)

        # Read type1 and tagX after 1, expect no events.
        read_response = recorder.read(query_type1_tag_x, after=1 + initial_position)
        result = list(read_response)
        self.assertEqual(0, len(result))
        self.assertEqual(3 + initial_position, read_response.head)

        # Read events with tagA, expect two events.
        query_tag_a = DCBQuery(items=[DCBQueryItem(tags=["tagA"])])
        read_response = recorder.read(query_tag_a, after=initial_position)
        result = list(read_response)
        self.assertEqual(2, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(event3.data, result[1].event.data)
        self.assertEqual(3 + initial_position, read_response.head)

        # Read events with tagA and tagB, expect one event.
        query_tag_a_and_b = DCBQuery(items=[DCBQueryItem(tags=["tagA", "tagB"])])
        read_response = recorder.read(query_tag_a_and_b, after=initial_position)
        result = list(read_response)
        self.assertEqual(1, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(3 + initial_position, read_response.head)

        # Read events with tagB or tagC, expect two events.
        query_tag_b_or_c = DCBQuery(
            items=[
                DCBQueryItem(tags=["tagB"]),
                DCBQueryItem(tags=["tagC"]),
            ]
        )
        read_response = recorder.read(query_tag_b_or_c, after=initial_position)
        result = list(read_response)
        self.assertEqual(2, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(event3.data, result[1].event.data)
        self.assertEqual(3 + initial_position, read_response.head)

        # Read events with tagX or tagY, expect one event.
        query_tag_x_or_y = DCBQuery(
            items=[
                DCBQueryItem(tags=["tagX"]),
                DCBQueryItem(tags=["tagY"]),
            ]
        )
        read_response = recorder.read(query_tag_x_or_y, after=initial_position)
        result = list(read_response)
        self.assertEqual(1, len(result))
        self.assertEqual(event1.data, result[0].event.data)
        self.assertEqual(3 + initial_position, read_response.head)

        # Read events with type2 and tagA, expect one event.
        query_type2_tag_a = DCBQuery(
            items=[DCBQueryItem(types=["type2"], tags=["tagA"])]
        )
        read_response = recorder.read(query_type2_tag_a, after=initial_position)
        result = list(read_response)
        self.assertEqual(1, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(3 + initial_position, read_response.head)

        # Read events with type2 and tagA after 2, expect no events.
        query_type2_tag_a = DCBQuery(
            items=[DCBQueryItem(types=["type2"], tags=["tagA"])]
        )
        read_response = recorder.read(query_type2_tag_a, after=2 + initial_position)
        result = list(read_response)
        self.assertEqual(0, len(result))
        self.assertEqual(3 + initial_position, read_response.head)

        # Read events with type2 and tagA, expect one event.
        query_type2_tag_a = DCBQuery(
            items=[DCBQueryItem(types=["type2"], tags=["tagA"])]
        )
        read_response = recorder.read(query_type2_tag_a, after=initial_position)
        result = list(read_response)
        self.assertEqual(1, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(3 + initial_position, read_response.head)

        # Read events with type2 and tagB, or with type3 and tagC, expect two events.
        query_type2_tag_b_or_type3_tagc = DCBQuery(
            items=[
                DCBQueryItem(types=["type2"], tags=["tagB"]),
                DCBQueryItem(types=["type3"], tags=["tagC"]),
            ]
        )
        read_response = recorder.read(
            query_type2_tag_b_or_type3_tagc, after=initial_position
        )
        result = list(read_response)
        self.assertEqual(2, len(result), result)
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(event3.data, result[1].event.data)
        self.assertEqual(3 + initial_position, read_response.head)

        # Repeat with query items in different order, expect events in ascending order.
        query_type3_tag_c_or_type2_tag_b = DCBQuery(
            items=[
                DCBQueryItem(types=["type3"], tags=["tagC"]),
                DCBQueryItem(types=["type2"], tags=["tagB"]),
            ]
        )
        read_response = recorder.read(
            query_type3_tag_c_or_type2_tag_b, after=initial_position
        )
        result = list(read_response)
        self.assertEqual(2, len(result))
        self.assertEqual(event2.data, result[0].event.data)
        self.assertEqual(event3.data, result[1].event.data)
        self.assertEqual(3 + initial_position, read_response.head)

        # Append must fail if recorded events match condition.
        event4 = DCBEvent(type="type4", data=b"data4")

        # Fail because condition matches all.
        new = [event4]
        with self.assertRaises(IntegrityError):
            recorder.append(new, DCBAppendCondition())

        # Fail because condition matches all after 1.
        with self.assertRaises(IntegrityError):
            recorder.append(new, DCBAppendCondition(after=1))

        # Fail because condition matches type1.
        with self.assertRaises(IntegrityError):
            recorder.append(new, DCBAppendCondition(query_type1))

        # Fail because condition matches type2 after 1.
        with self.assertRaises(IntegrityError):
            recorder.append(new, DCBAppendCondition(query_type2, after=1))

        # Fail because condition matches tagX.
        with self.assertRaises(IntegrityError):
            recorder.append(new, DCBAppendCondition(query_tag_x))

        # Fail because condition matches tagA after 1.
        with self.assertRaises(IntegrityError):
            recorder.append(new, DCBAppendCondition(query_tag_a, after=1))

        # Fail because condition matches type1 and tagX.
        with self.assertRaises(IntegrityError):
            recorder.append(new, DCBAppendCondition(query_type1_tag_x))

        # Fail because condition matches type2 and tagA after 1.
        with self.assertRaises(IntegrityError):
            recorder.append(new, DCBAppendCondition(query_type2_tag_a, after=1))

        # Fail because condition matches tagA and tagB.
        with self.assertRaises(IntegrityError):
            recorder.append(new, DCBAppendCondition(query_tag_a_and_b))

        # Fail because condition matches tagB or tagC.
        with self.assertRaises(IntegrityError):
            recorder.append(new, DCBAppendCondition(query_tag_b_or_c))

        # Fail because condition matches tagX or tagY.
        with self.assertRaises(IntegrityError):
            recorder.append(new, DCBAppendCondition(query_tag_x_or_y))

        # Fail because condition matches with type2 and tagB, or with type3 and tagC.
        with self.assertRaises(IntegrityError):
            recorder.append(new, DCBAppendCondition(query_type2_tag_b_or_type3_tagc))

        # Can append after 3.
        recorder.append(new)

        # Can append match type_n.
        query_type_n = DCBQuery(items=[DCBQueryItem(types=["typeN"])])
        recorder.append(new, DCBAppendCondition(query_type_n))

        # Can append match tagY.
        recorder.append(new, DCBAppendCondition(query_tag_y))

        # Can append match type1 after 1.
        recorder.append(
            new, DCBAppendCondition(query_type1, after=1 + initial_position)
        )

        # Can append match tagX after 1.
        recorder.append(
            new, DCBAppendCondition(query_tag_x, after=1 + initial_position)
        )

        # Can append match type1 and tagX after 1.
        recorder.append(
            new, DCBAppendCondition(query_type1_tag_x, after=1 + initial_position)
        )

        # Can append match tagX, after 1.
        recorder.append(
            new, DCBAppendCondition(query_tag_x, after=1 + initial_position)
        )

        # Check it works with course subscription consistency boundaries and events.
        student_id = f"student1-{uuid4()}"
        student_registered = DCBEvent(
            type="StudentRegistered",
            data=json.dumps({"name": "Student1", "max_courses": 10}).encode(),
            tags=[student_id],
        )
        course_id = f"course1-{uuid4()}"
        course_registered = DCBEvent(
            type="CourseRegistered",
            data=json.dumps({"name": "Course1", "places": 10}).encode(),
            tags=[course_id],
        )
        student_joined_course = DCBEvent(
            type="StudentJoinedCourse",
            data=json.dumps(
                {"student_id": student_id, "course_id": course_id}
            ).encode(),
            tags=[course_id, student_id],
        )

        recorder.append(
            events=[student_registered],
            condition=DCBAppendCondition(
                fail_if_events_match=DCBQuery(
                    items=[
                        DCBQueryItem(
                            tags=student_registered.tags, types=["StudentRegistered"]
                        )
                    ],
                ),
                after=3,
            ),
        )
        recorder.append(
            events=[course_registered],
            condition=DCBAppendCondition(
                fail_if_events_match=DCBQuery(
                    items=[DCBQueryItem(tags=course_registered.tags)],
                ),
                after=3,
            ),
        )
        recorder.append(
            events=[student_joined_course],
            condition=DCBAppendCondition(
                fail_if_events_match=DCBQuery(
                    items=[DCBQueryItem(tags=student_joined_course.tags)],
                ),
                after=3,
            ),
        )

        read_response = recorder.read(after=initial_position)
        result = list(read_response)
        self.assertEqual(13, len(result))
        self.assertEqual(result[-3].event.type, student_registered.type)
        self.assertEqual(result[-2].event.type, course_registered.type)
        self.assertEqual(result[-1].event.type, student_joined_course.type)
        self.assertEqual(result[-3].event.data, student_registered.data)
        self.assertEqual(result[-2].event.data, course_registered.data)
        self.assertEqual(result[-1].event.data, student_joined_course.data)
        self.assertEqual(result[-3].event.tags, student_registered.tags)
        self.assertEqual(result[-2].event.tags, course_registered.tags)
        self.assertEqual(result[-1].event.tags, student_joined_course.tags)
        self.assertEqual(13 + initial_position, read_response.head)

        read_response = recorder.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=student_registered.tags)],
            ),
            after=initial_position,
        )
        self.assertEqual(2, len(list(read_response)))
        self.assertEqual(13 + initial_position, read_response.head)

        read_response = recorder.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=course_registered.tags)],
            ),
            after=initial_position,
        )
        self.assertEqual(2, len(list(read_response)))
        self.assertEqual(13 + initial_position, read_response.head)

        read_response = recorder.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=student_joined_course.tags)],
            ),
            after=initial_position,
        )
        self.assertEqual(1, len(list(read_response)))
        self.assertEqual(13 + initial_position, read_response.head)

        read_response = recorder.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=student_registered.tags)],
            ),
            after=2 + initial_position,
        )
        self.assertEqual(2, len(list(read_response)))
        self.assertEqual(13 + initial_position, read_response.head)

        read_response = recorder.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=course_registered.tags)],
            ),
            after=2 + initial_position,
        )
        self.assertEqual(2, len(list(read_response)))
        self.assertEqual(13 + initial_position, read_response.head)

        read_response = recorder.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=student_joined_course.tags)],
            ),
            after=2 + initial_position,
        )
        self.assertEqual(1, len(list(read_response)))
        self.assertEqual(13 + initial_position, read_response.head)

        read_response = recorder.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=student_registered.tags)],
            ),
            after=2 + initial_position,
            limit=1,
        )
        self.assertEqual(1, len(list(read_response)))
        self.assertEqual(11 + initial_position, read_response.head)

        read_response = recorder.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=course_registered.tags)],
            ),
            after=2 + initial_position,
            limit=1,
        )
        self.assertEqual(1, len(list(read_response)))
        self.assertEqual(12 + initial_position, read_response.head)

        read_response = recorder.read(
            query=DCBQuery(
                items=[DCBQueryItem(tags=student_joined_course.tags)],
            ),
            after=2 + initial_position,
            limit=1,
        )
        self.assertEqual(1, len(list(read_response)))
        self.assertEqual(13 + initial_position, read_response.head)

        consistency_boundary = DCBQuery(
            items=[
                DCBQueryItem(
                    types=["StudentRegistered", "StudentJoinedCourse"],
                    tags=[student_id],
                ),
                DCBQueryItem(
                    types=["CourseRegistered", "StudentJoinedCourse"],
                    tags=[course_id],
                ),
            ]
        )
        read_response = recorder.read(
            query=consistency_boundary,
            after=initial_position,
        )
        self.assertEqual(3, len(list(read_response)))
        self.assertEqual(13 + initial_position, read_response.head)

        # # Check it works with appointment booking.
        # appointment_id = f"appointment-{uuid4()}"
        # tags = [
        #     f"slot:2025-07-10-{hour:02}-{minute:02}"
        #     for hour in range(13, 18)
        #     for minute in range(0, 60)
        # ]
        # appointment_scheduled = DCBEvent(
        #     type="AppointmentSchedules",
        #     data=json.dumps({"name": "ABC"}).encode(),
        #     tags=tags,
        # )
        # started = datetime.datetime.now()
        # eventstore.append(
        #     events=[appointment_scheduled],
        #     condition=DCBAppendCondition(
        #         fail_if_events_match=DCBQuery(
        #             items=[DCBQueryItem(tags=tags)],
        #         ),
        #     ),
        # )
        # print("Event appended:", datetime.datetime.now() - started)
        # started = datetime.datetime.now()
        # with self.assertRaises(IntegrityError):
        #     eventstore.append(
        #         events=[appointment_scheduled],
        #         condition=DCBAppendCondition(
        #             fail_if_events_match=DCBQuery(
        #                 items=[DCBQueryItem(tags=tags)],
        #             ),
        #         ),
        #     )
        # print("Conflict detected:", datetime.datetime.now() - started)

    def _test_append_subscribe(
        self, recorder: DCBRecorder, initial_position: int = 0
    ) -> None:
        # Append one event.
        event1 = DCBEvent(type="type1", data=b"data1", tags=["tagX"])
        position1 = recorder.append(events=[event1])
        self.assertEqual(1 + initial_position, position1)

        # Start subscription.
        with recorder.subscribe(after=initial_position) as subscription:
            self.assertEqual(position1, next(subscription).position)

            thread = EnsureSubscriptionBlockAndReceive(subscription)
            thread.has_blocked.wait()
            self.assertFalse(thread.has_received.wait(timeout=0.5))

            # Append one more event.
            event2 = DCBEvent(type="type1", data=b"data1", tags=["tagX"])
            position2 = recorder.append(events=[event2])
            self.assertEqual(2 + initial_position, position2)

            self.assertTrue(thread.has_received.wait(timeout=1))
            assert thread.received_event is not None  # for mypy
            self.assertEqual(position2, thread.received_event.position)


class EnsureSubscriptionBlockAndReceive(threading.Thread):
    def __init__(self, subscription: DCBSubscription[TDCBRecorder_co]):
        super().__init__()
        self.subscription = subscription
        self.has_blocked = threading.Event()
        self.has_received = threading.Event()
        self.received_event: DCBSequencedEvent | None = None
        self.start()

    def run(self) -> None:
        self.has_blocked.set()
        self.received_event = next(self.subscription)
        self.has_received.set()
