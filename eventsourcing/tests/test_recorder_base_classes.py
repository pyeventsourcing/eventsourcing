from unittest import TestCase

from eventsourcing.persistence import (
    AsyncAggregateRecorder,
    AsyncApplicationRecorder,
    AsyncProcessRecorder,
    SyncAggregateRecorder,
    SyncApplicationRecorder,
    SyncProcessRecorder,
)
from eventsourcing.tests.asyncio_testcase import IsolatedAsyncioTestCase


class MySyncAggregateRecorder(SyncAggregateRecorder):
    def insert_events(*args, **kwargs):
        pass

    def select_events(*args, **kwargs):
        pass


class MySyncApplicationRecorder(MySyncAggregateRecorder, SyncApplicationRecorder):
    def select_notifications(*args, **kwargs):
        pass

    def max_notification_id(self):
        pass


class MySyncProcessRecorder(MySyncApplicationRecorder, SyncProcessRecorder):
    def max_tracking_id(*args):
        pass


class MyAsyncAggregateRecorder(AsyncAggregateRecorder):
    async def async_insert_events(*args, **kwargs):
        pass

    async def async_select_events(*args, **kwargs):
        pass


class MyAsyncApplicationRecorder(MyAsyncAggregateRecorder, AsyncApplicationRecorder):
    async def async_select_notifications(*args, **kwargs):
        pass

    async def async_max_notification_id(self):
        pass


class MyAsyncProcessRecorder(MyAsyncApplicationRecorder, AsyncProcessRecorder):
    async def async_max_tracking_id(*args):
        pass


class TestSyncRecorderClassesRaiseNotImplementedError(IsolatedAsyncioTestCase):
    async def test_aggregate_recorder(self):
        recorder = MySyncAggregateRecorder()
        with self.assertRaises(NotImplementedError):
            await recorder.async_insert_events([])
        with self.assertRaises(NotImplementedError):
            await recorder.async_select_events(None)

    async def test_application_recorder(self):
        recorder = MySyncApplicationRecorder()
        with self.assertRaises(NotImplementedError):
            await recorder.async_select_notifications(1, 1)
        with self.assertRaises(NotImplementedError):
            await recorder.async_max_notification_id()

    async def test_process_recorder(self):
        recorder = MySyncProcessRecorder()
        with self.assertRaises(NotImplementedError):
            await recorder.async_max_tracking_id("")


class TestAsyncRecorderClassesRaiseNotImplementedError(TestCase):
    def test_aggregate_recorder(self):
        recorder = MyAsyncAggregateRecorder()
        with self.assertRaises(NotImplementedError):
            recorder.insert_events([])
        with self.assertRaises(NotImplementedError):
            recorder.select_events(None)

    def test_application_recorder(self):
        recorder = MyAsyncApplicationRecorder()
        with self.assertRaises(NotImplementedError):
            recorder.select_notifications(1, 1)
        with self.assertRaises(NotImplementedError):
            recorder.max_notification_id()

    def test_process_recorder(self):
        recorder = MyAsyncProcessRecorder()
        with self.assertRaises(NotImplementedError):
            recorder.max_tracking_id("")
