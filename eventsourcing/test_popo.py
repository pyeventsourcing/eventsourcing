from eventsourcing.infrastructure_testcases import InfrastructureFactoryTestCase
from eventsourcing.poporecorders import POPOAggregateRecorder, POPOApplicationRecorder, \
    POPOProcessRecorder
from eventsourcing.aggregaterecorder_testcase import AggregateRecorderTestCase
from eventsourcing.applicationrecorder_testcase import ApplicationRecorderTestCase
from eventsourcing.processrecorder_testcase import ProcessRecordsTestCase


class TestPopoAggregateRecorder(AggregateRecorderTestCase):
    def create_recorder(self):
        return POPOAggregateRecorder()


class TestPOPOApplicationRecorder(
    ApplicationRecorderTestCase
):
    def create_recorder(self):
        return POPOApplicationRecorder()


class TestPOPOProcessRecorder(ProcessRecordsTestCase):
    def create_recorder(self):
        return POPOProcessRecorder()

    def test_performance(self):
        super().test_performance()


class TestPOPOInfrastructureFactory(
    InfrastructureFactoryTestCase
):
    pass


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
del ProcessRecordsTestCase
del InfrastructureFactoryTestCase
