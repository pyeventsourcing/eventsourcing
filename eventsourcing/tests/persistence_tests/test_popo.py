from eventsourcing.popo import (
    Factory,
    POPOAggregateRecorder,
    POPOApplicationRecorder,
    POPOProcessRecorder,
)
from eventsourcing.tests.persistence_tests.base_aggregate_recorder_tests import (
    AggregateRecorderTestCase,
)
from eventsourcing.tests.persistence_tests.base_application_recorder_tests import (
    ApplicationRecorderTestCase,
)
from eventsourcing.tests.persistence_tests.base_infrastructure_tests import (
    InfrastructureFactoryTestCase,
)
from eventsourcing.tests.persistence_tests.base_process_recorder_tests import (
    ProcessRecorderTestCase,
)
from eventsourcing.utils import Environment


class TestPOPOAggregateRecorder(AggregateRecorderTestCase):
    def create_recorder(self):
        return POPOAggregateRecorder()


class TestPOPOApplicationRecorder(ApplicationRecorderTestCase):
    def create_recorder(self):
        return POPOApplicationRecorder()


class TestPOPOProcessRecorder(ProcessRecorderTestCase):
    def create_recorder(self):
        return POPOProcessRecorder()

    def test_performance(self):
        super().test_performance()


class TestPOPOInfrastructureFactory(InfrastructureFactoryTestCase):
    def setUp(self) -> None:
        self.env = Environment("TestCase")
        super().setUp()

    def expected_factory_class(self):
        return Factory

    def expected_aggregate_recorder_class(self):
        return POPOAggregateRecorder

    def expected_application_recorder_class(self):
        return POPOApplicationRecorder

    def expected_process_recorder_class(self):
        return POPOProcessRecorder


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
del ProcessRecorderTestCase
del InfrastructureFactoryTestCase
