from eventsourcing.popo import (
    POPOAggregateRecorder,
    POPOApplicationRecorder,
    POPOProcessRecorder,
)
from eventsourcing.tests.async_aggregaterecorder_testcase import (
    AsyncAggregateRecorderTestCase,
)
from eventsourcing.tests.async_applicationrecorder_testcase import (
    AsyncApplicationRecorderTestCase,
)
from eventsourcing.tests.async_processrecorder_testcase import (
    AsyncProcessRecorderTestCase,
)


class TestPOPOAggregateRecorder(AsyncAggregateRecorderTestCase):
    def create_recorder(self):
        return POPOAggregateRecorder()


class TestPOPOApplicationRecorder(AsyncApplicationRecorderTestCase):
    def create_recorder(self):
        return POPOApplicationRecorder()


class TestPOPOProcessRecorder(AsyncProcessRecorderTestCase):
    def create_recorder(self):
        return POPOProcessRecorder()


del AsyncAggregateRecorderTestCase
del AsyncApplicationRecorderTestCase
del AsyncProcessRecorderTestCase
