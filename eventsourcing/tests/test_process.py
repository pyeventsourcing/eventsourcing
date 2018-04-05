from unittest import TestCase
from uuid import uuid4

from eventsourcing.application.process import Process, RepositoryWrapper
from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.domain.model.events import clear_event_handlers


class TestProcess(TestCase):

    def test_process_with_example_policy(self):
        # Construct example process.
        process = Process(
            'test',
            policy=example_policy,
            persist_event_type=ExampleAggregate.Event,
            setup_tables=True,
        )

        # Make the process follow itself.
        process.follow('test', process.notification_log)

        # Create an aggregate.
        aggregate2 = ExampleAggregate.__create__()
        aggregate2.__save__()

        # Check the aggregate has been automatically "moved on".
        self.assertTrue(process.repository[aggregate2.id].moved_on)

        # Check the __contains__ method of the repo wrapper.
        self.assertTrue(aggregate2.id in RepositoryWrapper(process.repository))
        self.assertFalse(uuid4() in RepositoryWrapper(process.repository))

        # Check the repository wrapper tracks causal dependencies.
        repository = RepositoryWrapper(process.repository)
        aggregate2 = repository[aggregate2.id]
        causal_dependencies = repository.causal_dependencies
        self.assertEqual(len(causal_dependencies), 1)
        self.assertEqual((aggregate2.id, aggregate2.__version__), causal_dependencies[0])

    def tearDown(self):
        clear_event_handlers()


# Example aggregate (used in the test).

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


def example_policy(process, repository, event):
    # Whenever an aggregate is created, then "move it on".
    if isinstance(event, ExampleAggregate.Created):
        # Get aggregate and move it on.
        aggregate = repository[event.originator_id]

        assert isinstance(aggregate, ExampleAggregate)
        aggregate.move_on()
