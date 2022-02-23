from eventsourcing.persistence import Tracking
from eventsourcing.popo import (
    Factory,
    POPOAggregateRecorder,
    POPOApplicationRecorder,
    POPOProcessRecorder,
)
from eventsourcing.tests.persistence import (
    AggregateRecorderTestCase,
    ApplicationRecorderTestCase,
    InfrastructureFactoryTestCase,
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

    def test_max_doesnt_increase_when_lower_inserted_later(self) -> None:
        # Construct the recorder.
        recorder = self.create_recorder()

        tracking1 = Tracking(
            application_name="upstream_app",
            notification_id=1,
        )
        tracking2 = Tracking(
            application_name="upstream_app",
            notification_id=2,
        )

        # Insert tracking info.
        recorder.insert_events(
            stored_events=[],
            tracking=tracking2,
        )

        # Get current position.
        self.assertEqual(
            recorder.max_tracking_id("upstream_app"),
            2,
        )

        # Insert tracking info.
        recorder.insert_events(
            stored_events=[],
            tracking=tracking1,
        )

        # Get current position.
        self.assertEqual(
            recorder.max_tracking_id("upstream_app"),
            2,
        )


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
