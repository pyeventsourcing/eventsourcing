from unittest import TestCase

from eventsourcing.application.process import Process
from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.domain.model.decorators import subscribe_to
from eventsourcing.domain.model.events import clear_event_handlers


class ExampleAggregate(AggregateRoot):
    def __init__(self, **kwargs):
        super(ExampleAggregate, self).__init__(**kwargs)
        self.moved_on = False

    class Event(AggregateRoot.Event):
        pass

    class Created(Event, AggregateRoot.Created):
        pass

    def move_on(self):
        self.__trigger_event__(ExampleAggregate.MovedOn)

    class MovedOn(Event):
        def mutate(self, aggregate):
            assert isinstance(aggregate, ExampleAggregate)
            aggregate.moved_on = True


def example_policy(process, event):
    unsaved_aggregates = []
    causal_dependencies = []

    # Whenever an aggregate is created, then "move it on".
    if isinstance(event, ExampleAggregate.Created):
        # Get aggregate and move it on.
        aggregate = process.get_originator(event)
        originator_id = aggregate.id
        originator_version = aggregate.__version__
        causal_dependencies.append((originator_id, originator_version))

        assert isinstance(aggregate, ExampleAggregate)
        aggregate.move_on()

        unsaved_aggregates.append(aggregate)

    return unsaved_aggregates, causal_dependencies


class TestProcess(TestCase):

    def tearDown(self):
        clear_event_handlers()

    def test_process_with_example_policy(self):

        # Construct example process.
        process = Process(policy=example_policy)

        # Check it has a notification log.
        self.assertTrue(process.notification_log)

        # Make the process follow itself.
        process.follow(process.notification_log, 'self')

        # Check no tracking records have been written.
        self.assertEqual(process.tracking_record_manager.get_max_record_id(upstream_application_name='self'), None)

        @subscribe_to(ExampleAggregate.Event)
        def prompt_process(_):
            while process.run():
                pass

        # Create an aggregate.
        aggregate2 = ExampleAggregate.__create__()
        aggregate2.__save__()

        # Check the aggregate has been "moved on".
        self.assertTrue(process.repository[aggregate2.id].moved_on)
