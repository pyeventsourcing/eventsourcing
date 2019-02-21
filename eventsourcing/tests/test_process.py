from unittest import TestCase
from uuid import uuid4

from eventsourcing.application.command import CommandProcess
from eventsourcing.application.process import ProcessApplication, ProcessApplicationWithSnapshotting, RepositoryWrapper
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.domain.model.aggregate import AggregateRoot, BaseAggregateRoot
from eventsourcing.domain.model.command import Command
from eventsourcing.domain.model.events import EventHandlersNotEmptyError, assert_event_handlers_empty, \
    clear_event_handlers, subscribe, unsubscribe
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.exceptions import CausalDependencyFailed, PromptFailed
from eventsourcing.utils.topic import resolve_topic
from eventsourcing.utils.transcoding import json_loads


class TestProcess(TestCase):
    process_class = SQLAlchemyApplication

    def test_process_with_example_policy(self):
        # Construct example process.
        process_class = ProcessApplication.mixin(self.process_class)
        with process_class(
            name='test',
            policy=example_policy,
            persist_event_type=ExampleAggregate.Event,
            setup_table=True,
        ) as process:
            # Make the process follow itself.
            process.follow('test', process.notification_log)

            # Create an aggregate.
            aggregate = ExampleAggregate.__create__()
            aggregate.__save__()

            # Run the process.
            process.run()

            # Check the aggregate has been "moved on".
            self.assertTrue(process.repository[aggregate.id].is_moved_on)

            # Check the __contains__ method of the repo wrapper.
            self.assertIn(aggregate.id, RepositoryWrapper(process.repository))
            self.assertNotIn(uuid4(), RepositoryWrapper(process.repository))

            # Check the repository wrapper tracks causal dependencies.
            repository = RepositoryWrapper(process.repository)
            aggregate = repository[aggregate.id]
            causal_dependencies = repository.causal_dependencies
            self.assertEqual(len(causal_dependencies), 1)
            self.assertEqual((aggregate.id, 1), causal_dependencies[0])

            # Check events from more than one aggregate are stored.
            self.assertIn(aggregate.second_id, process.repository)

    def test_process_application_with_snapshotting(self):
        # Construct example process.
        with ProcessApplicationWithSnapshotting.mixin(self.process_class)(
            name='test',
            policy=example_policy,
            persist_event_type=ExampleAggregate.Event,
            setup_table=True,
            snapshot_period=2,
        ) as process:
            # Make the process follow itself.
            process.follow('test', process.notification_log)

            # Create an aggregate.
            aggregate = ExampleAggregate.__create__()

            # Check there isn't a snapshot.
            self.assertIsNone(process.snapshot_strategy.get_snapshot(aggregate.id))

            # Should "move on" by the process following itself.
            aggregate.__save__()
            process.run()

            aggregate = process.repository[aggregate.id]
            self.assertEqual(1, aggregate.__version__)

            # Check there is a snapshot.
            snapshot = process.snapshot_strategy.get_snapshot(aggregate.id)
            self.assertIsInstance(snapshot, Snapshot)
            self.assertEqual(snapshot.originator_version, 1)

            snapshot_v0 = process.snapshot_strategy.get_snapshot(aggregate.id, lt=snapshot.originator_version)
            self.assertIsNone(snapshot_v0, Snapshot)

    def test_causal_dependencies(self):
        # Try to process an event that has unresolved causal dependencies.
        pipeline_id1 = 0
        pipeline_id2 = 1

        # Create two events, one has causal dependency on the other.
        process_class = ProcessApplication.mixin(self.process_class)
        core1 = process_class(
            name='core',
            # persist_event_type=ExampleAggregate.Created,
            persist_event_type=BaseAggregateRoot.Event,
            setup_table=True,
            pipeline_id=pipeline_id1,
        )
        core1.use_causal_dependencies = True

        # Needed for SQLAlchemy only.
        kwargs = {'session': core1.session} if hasattr(core1, 'session') else {}

        core2 = process_class(
            name='core',
            pipeline_id=pipeline_id2,
            policy=example_policy,
            **kwargs
        )
        core2.use_causal_dependencies = True

        # First event in pipeline 1.
        aggregate = ExampleAggregate.__create__()
        aggregate.__save__()

        # Second event in pipeline 2.
        # - it's important this is done in a policy so the causal dependencies are identified
        core2.follow('core', core1.notification_log)
        core2.run()

        # Check the aggregate exists.
        self.assertTrue(aggregate.id in core1.repository)

        # Check the aggregate has been "moved on".
        aggregate = core1.repository[aggregate.id]
        self.assertTrue(aggregate.is_moved_on)
        self.assertTrue(aggregate.second_id)
        self.assertIn(aggregate.second_id, core1.repository)

        # Check the events have different pipeline IDs.
        aggregate_records = core1.event_store.record_manager.get_records(aggregate.id)
        second_entity_records = core1.event_store.record_manager.get_records(aggregate.second_id)

        self.assertEqual(2, len(aggregate_records))
        self.assertEqual(1, len(second_entity_records))

        self.assertEqual(pipeline_id1, aggregate_records[0].pipeline_id)
        self.assertEqual(pipeline_id2, aggregate_records[1].pipeline_id)
        self.assertEqual(pipeline_id2, second_entity_records[0].pipeline_id)

        # Check the causal dependencies have been constructed.
        # - the first 'Created' event doesn't have an causal dependencies
        self.assertFalse(aggregate_records[0].causal_dependencies)

        # - the second 'Created' event depends on the Created event in another pipeline.
        expect = [{
            'notification_id': 1,
            'pipeline_id': pipeline_id1
        }]
        actual = json_loads(second_entity_records[0].causal_dependencies)

        self.assertEqual(expect, actual)

        # - the 'AttributeChanged' event depends on the second Created,
        # which is in the same pipeline, so expect no causal dependencies.
        self.assertFalse(aggregate_records[1].causal_dependencies)

        # Setup downstream process.
        downstream1 = process_class(
            'downstream',
            pipeline_id=pipeline_id1,
            policy=event_logging_policy,
            **kwargs
        )
        downstream1.follow('core', core1.notification_log)
        downstream2 = process_class(
            'downstream',
            pipeline_id=pipeline_id2,
            policy=event_logging_policy,
            **kwargs
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
        self.assertEqual(2, len(downstream2.event_store.record_manager.get_notifications()))

        core1.close()
        core2.close()
        downstream1.close()
        downstream2.close()

    def test_handle_prompt_failed(self):
        process = ProcessApplication.mixin(self.process_class)(
            name='test',
            policy=example_policy,
            persist_event_type=ExampleAggregate.Event,
            setup_table=True,
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
        try:
            assert_event_handlers_empty()
        except EventHandlersNotEmptyError:
            clear_event_handlers()
            raise


class TestCommands(TestCase):
    process_class = SQLAlchemyApplication

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
        commands = CommandProcess.mixin(self.process_class)(
            setup_table=True
        )
        core = ProcessApplication.mixin(self.process_class)(
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

class ExampleAggregate(BaseAggregateRoot):
    def __init__(self, **kwargs):
        super(ExampleAggregate, self).__init__(**kwargs)
        self.is_moved_on = False
        self.second_id = None

    class Event(BaseAggregateRoot.Event):
        pass

    class Created(Event, BaseAggregateRoot.Created):
        pass

    def move_on(self, second_id=None):
        self.__trigger_event__(ExampleAggregate.MovedOn, second_id=second_id)

    class MovedOn(Event):
        @property
        def second_id(self):
            return self.__dict__['second_id']

        def mutate(self, aggregate):
            assert isinstance(aggregate, ExampleAggregate)
            aggregate.is_moved_on = True
            aggregate.second_id = self.second_id


def example_policy(repository, event):
    # Whenever an aggregate is created, then "move it on".
    if isinstance(event, ExampleAggregate.Created):
        # Get aggregate and move it on.
        aggregate = repository[event.originator_id]

        assert isinstance(aggregate, ExampleAggregate)

        # Also create a second entity, allows test to check that
        # events from more than one entity are stored.
        second_id = uuid4()
        other_entity = AggregateRoot.__create__(originator_id=second_id)
        aggregate.move_on(second_id=second_id)
        return other_entity

    elif isinstance(event, Command.Created):
        command_class = resolve_topic(event.originator_topic)
        if command_class is CreateExample:
            return ExampleAggregate.__create__()


class LogMessage(BaseAggregateRoot):

    def __init__(self, message='', **kwargs):
        super(LogMessage, self).__init__(**kwargs)
        self.message = message

    class Event(BaseAggregateRoot.Event):
        pass

    class Created(Event, BaseAggregateRoot.Created):
        pass


def event_logging_policy(_, event):
    return LogMessage.__create__(uuid4(), message=str(event))


class CreateExample(Command):
    pass
