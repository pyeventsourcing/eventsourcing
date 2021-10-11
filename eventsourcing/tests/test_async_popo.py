from eventsourcing.popo import (
    Factory,
    POPOAggregateRecorder,
    POPOApplicationRecorder,
    POPOAsyncAggregateRecorder,
    POPOAsyncApplicationRecorder,
    POPOAsyncProcessRecorder,
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
from eventsourcing.tests.infrastructure_testcases import (
    InfrastructureFactoryTestCase,
)


class TestPOPOAsyncAggregateRecorder(AsyncAggregateRecorderTestCase):
    def create_recorder(self):
        return POPOAsyncAggregateRecorder()


class TestPOPOAsyncApplicationRecorder(AsyncApplicationRecorderTestCase):
    def create_recorder(self):
        return POPOAsyncApplicationRecorder()


class TestPOPOAsyncProcessRecorder(AsyncProcessRecorderTestCase):
    def create_recorder(self):
        return POPOAsyncProcessRecorder()


class TestPOPOInfrastructureFactory(InfrastructureFactoryTestCase):
    def expected_factory_class(self):
        return Factory

    def expected_aggregate_recorder_class(self):
        return POPOAggregateRecorder

    def expected_application_recorder_class(self):
        return POPOApplicationRecorder

    def expected_process_recorder_class(self):
        return POPOProcessRecorder


del AsyncAggregateRecorderTestCase
del AsyncApplicationRecorderTestCase
del AsyncProcessRecorderTestCase
del InfrastructureFactoryTestCase
