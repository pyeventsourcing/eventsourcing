from unittest import TestCase
from uuid import uuid4

from eventsourcing.application.process import Process, RepositoryWrapper
from eventsourcing.application.command import CommandProcess
from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.domain.model.command import Command
from eventsourcing.domain.model.events import assert_event_handlers_empty, subscribe, unsubscribe
from eventsourcing.exceptions import CausalDependencyFailed, PromptFailed
from eventsourcing.utils.topic import resolve_topic
from eventsourcing.utils.transcoding import json_loads


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
        self.assertTrue(process.repository[aggregate2.id].is_moved_on)

        # Check the __contains__ method of the repo wrapper.
        self.assertTrue(aggregate2.id in RepositoryWrapper(process.repository))
        self.assertFalse(uuid4() in RepositoryWrapper(process.repository))

        # Check the repository wrapper tracks causal dependencies.
        repository = RepositoryWrapper(process.repository)
        aggregate2 = repository[aggregate2.id]
        causal_dependencies = repository.causal_dependencies
        self.assertEqual(len(causal_dependencies), 1)
        self.assertEqual((aggregate2.id, 1), causal_dependencies[0])

        process.close()

    def test_causal_dependencies(self):
        # Try to process an event that has unresolved causal dependencies.
        pipeline_id1 = 0
        pipeline_id2 = 1

        # Create two events, one has causal dependency on the other.
        core1 = Process(
            'core',
            persist_event_type=ExampleAggregate.Created,
            setup_tables=True,
            pipeline_id=pipeline_id1,
        )

        core2 = Process(
            'core',
            pipeline_id=pipeline_id2,
            policy=example_policy,
            session=core1.session
        )

        # First event in partition 1.
        aggregate = ExampleAggregate.__create__()
        aggregate.__save__()

        # Second event in partition 2.
        # - it's important this is done in a policy so the causal dependency is identified
        core2.follow('core', core1.notification_log)
        core2.run()

        # Check the aggregate exists.
        self.assertTrue(aggregate.id in core1.repository)

        # Check the aggregate has been "moved on".
        self.assertTrue(core1.repository[aggregate.id].is_moved_on)

        # Check the events have different partition IDs.
        records = core1.event_store.record_manager.get_records(aggregate.id)
        self.assertEqual(2, len(records))
        self.assertEqual(pipeline_id1, records[0].pipeline_id)

        # Check the causal dependencies have been constructed.
        self.assertEqual(None, records[0].causal_dependencies)
        self.assertTrue({
            'notification_id': 1,
            'pipeline_id': pipeline_id1
        }, json_loads(records[1].causal_dependencies))

        # Setup downstream process.
        downstream1 = Process(
            'downstream',
            pipeline_id=pipeline_id1,
            session=core1.session,
            policy=event_logging_policy,
        )
        downstream1.follow('core', core1.notification_log)
        downstream2 = Process(
            'downstream',
            pipeline_id=pipeline_id2,
            session=core1.session,
            policy=event_logging_policy,
        )
        downstream2.follow('core', core2.notification_log)

        # Try to process pipeline 2, should fail due to causal dependency.
        with self.assertRaises(CausalDependencyFailed):
            downstream2.run()

        self.assertEqual(0, len(downstream1.event_store.record_manager.get_notifications()))
        self.assertEqual(0, len(downstream2.event_store.record_manager.get_notifications()))

        # Try to process pipeline 1, should work.
        downstream1.run()

        self.assertEqual(1, len(downstream1.event_store.record_manager.get_notifications()))
        self.assertEqual(0, len(downstream2.event_store.record_manager.get_notifications()))

        # Try again to process pipeline 2, should work this time.
        downstream2.run()

        self.assertEqual(1, len(downstream1.event_store.record_manager.get_notifications()))
        self.assertEqual(1, len(downstream2.event_store.record_manager.get_notifications()))

        core1.close()
        core2.close()
        downstream1.close()
        downstream2.close()

    def test_handle_prompt_failed(self):
        process = Process(
            'test',
            policy=example_policy,
            persist_event_type=ExampleAggregate.Event,
            setup_tables=True,
        )

        def raise_exception(_):
            raise Exception()

        def raise_prompt_failed(_):
            raise PromptFailed()

        subscribe(raise_exception)
        try:
            with self.assertRaises(PromptFailed):
                process.publish_prompt()
        finally:
            unsubscribe(raise_exception)

        subscribe(raise_prompt_failed)
        try:
            with self.assertRaises(PromptFailed):
                process.publish_prompt()
        finally:
            unsubscribe(raise_prompt_failed)

        try:
            process.publish_prompt()
        finally:
            process.close()

    def tearDown(self):
        assert_event_handlers_empty()


class TestCommands(TestCase):

    def test_command_aggregate(self):
        # Create a command.
        cmd = Command.__create__()
        assert isinstance(cmd, Command)

        # Check is_done gets changed by done()
        self.assertFalse(cmd.is_done)
        cmd.done()
        self.assertTrue(cmd.is_done)

        # Check the resulting domain events.
        pending_events = cmd.__batch_pending_events__()
        self.assertIsInstance(pending_events[0], Command.Created)
        self.assertIsInstance(pending_events[1], Command.Done)

    def test_command_process(self):
        commands = CommandProcess(
            setup_tables=True
        )
        core = Process(
            'core',
            policy=example_policy,
            session=commands.session
        )

        self.assertFalse(list(commands.event_store.all_domain_events()))

        cmd = CreateExample.__create__()
        # cmd = Command.__create__(cmd_method='create_example', cmd_args={})
        cmd.__save__()

        domain_events = list(commands.event_store.all_domain_events())
        # self.assertTrue(domain_events)
        self.assertEqual(len(domain_events), 1)

        self.assertFalse(list(core.event_store.all_domain_events()))

        core.follow('commands', commands.notification_log)
        core.run()

        self.assertTrue(list(core.event_store.all_domain_events()))

        commands.close()
        core.close()

    def tearDown(self):
        assert_event_handlers_empty()


# Example aggregate (used in the test).

class ExampleAggregate(AggregateRoot):
    def __init__(self, **kwargs):
        super(ExampleAggregate, self).__init__(**kwargs)
        self.is_moved_on = False

    class Event(AggregateRoot.Event):
        pass

    class Created(Event, AggregateRoot.Created):
        pass

    def move_on(self):
        self.__trigger_event__(ExampleAggregate.MovedOn)

    class MovedOn(Event):
        def mutate(self, aggregate):
            assert isinstance(aggregate, ExampleAggregate)
            aggregate.is_moved_on = True


def example_policy(process, repository, event):
    # Whenever an aggregate is created, then "move it on".
    if isinstance(event, ExampleAggregate.Created):
        # Get aggregate and move it on.
        aggregate = repository[event.originator_id]

        assert isinstance(aggregate, ExampleAggregate)
        aggregate.move_on()

    elif isinstance(event, Command.Created):
        command_class = resolve_topic(event.originator_topic)
        if command_class is CreateExample:
            return ExampleAggregate.__create__()


class LogMessage(AggregateRoot):

    def __init__(self, message='', **kwargs):
        super(LogMessage, self).__init__(**kwargs)
        self.message = message

    class Event(AggregateRoot.Event):
        pass

    class Created(Event, AggregateRoot.Created):
        pass


def event_logging_policy(process, repository, event):
    return LogMessage.__create__(uuid4(), message=str(event))


class CreateExample(Command):
    pass
