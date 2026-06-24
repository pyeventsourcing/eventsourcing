from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4

from eventsourcing.persistence import (
    ApplicationRecorder,
    ListenNotifySubscription,
    Notification,
    NullTranscoder,
    ProgrammingError,
)


class TestNullTranscoder(TestCase):
    def test(self) -> None:
        t = NullTranscoder()
        with self.assertRaises(ProgrammingError):
            t.encode(None)
        with self.assertRaises(ProgrammingError):
            t.decode(b"")


class TestListNotifySubscriptionSubscription(TestCase):
    def test_listen_catches_error(self) -> None:

        mock_recorder = Mock(spec=ApplicationRecorder)

        subscription = ListenNotifySubscription(mock_recorder, 0)

        # self.assertIsInstance(subscription._thread_error, TypeError)

        with self.assertRaises(TypeError):
            next(subscription)

        with self.assertRaises(TypeError):
            next(subscription)

        subscription._thread_error = None

        with self.assertRaises(StopIteration):
            next(subscription)

        subscription._notifications = [
            Notification(
                id=1, originator_id=uuid4(), originator_version=1, topic="", state=b""
            ),
            Notification(
                id=2, originator_id=uuid4(), originator_version=1, topic="", state=b""
            ),
            Notification(
                id=3, originator_id=uuid4(), originator_version=1, topic="", state=b""
            ),
        ]
        subscription._notifications_index = 0

        subscription._has_been_stopped = False
        self.assertEqual(1, next(subscription).id)
        self.assertEqual(2, next(subscription).id)
        self.assertEqual(3, next(subscription).id)

        subscription.stop()

        with self.assertRaises(StopIteration):
            next(subscription)

        subscription._notifications = [
            Notification(
                id=4, originator_id=uuid4(), originator_version=1, topic="", state=b""
            ),
            Notification(
                id=5, originator_id=uuid4(), originator_version=1, topic="", state=b""
            ),
            Notification(
                id=6, originator_id=uuid4(), originator_version=1, topic="", state=b""
            ),
        ]
        subscription._notifications_index = 0
        subscription._thread_error = ValueError()
        subscription._has_been_stopped = True

        with self.assertRaises(ValueError):
            next(subscription)

        with self.assertRaises(ProgrammingError):
            subscription.__exit__(None, None, None)

        subscription.__enter__()
        with self.assertRaises(ProgrammingError):
            subscription.__enter__()

        subscription._has_been_stopped = False
        subscription._thread_error = None
        subscription._loop_on_pull()
        self.assertIsInstance(subscription._thread_error, TypeError)
        subscription._has_been_stopped = False
        subscription._thread_error = ValueError()
        subscription._loop_on_pull()
        self.assertIsInstance(subscription._thread_error, ValueError)
