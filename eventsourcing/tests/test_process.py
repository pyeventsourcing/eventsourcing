from decimal import Decimal
from unittest import TestCase
from uuid import uuid4

from sqlalchemy import Column, Text
from sqlalchemy_utils import UUIDType

from eventsourcing.application.command import CommandProcess
from eventsourcing.application.process import (
    ProcessApplication,
    ProcessApplicationWithSnapshotting,
    WrappedRepository,
)
from eventsourcing.application.simple import PromptToPull
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.domain.model.aggregate import AggregateRoot, BaseAggregateRoot
from eventsourcing.domain.model.command import Command
from eventsourcing.domain.model.events import (
    EventHandlersNotEmptyError,
    assert_event_handlers_empty,
    clear_event_handlers,
    subscribe,
    unsubscribe,
)
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.exceptions import (
    CausalDependencyFailed,
    ProgrammingError,
    PromptFailed,
)
from eventsourcing.infrastructure.sqlalchemy.records import Base
from eventsourcing.utils.topic import resolve_topic
from eventsourcing.utils.transcoding import ObjectJSONDecoder
from eventsourcing.whitehead import TEntity


class TestProcessApplication(TestCase):
    infrastructure_class = SQLAlchemyApplication

    def test_process_with_example_policy(self):
        # Construct example process.
        process_class = ProcessApplication.mixin(self.infrastructure_class)
        with process_class(
            name="test",
            policy=example_policy,
            persist_event_type=ExampleAggregate.Event,
            setup_table=True,
        ) as process:
            # Make the process follow itself.
            process.follow("test", process.notification_log)

            # Create an aggregate.
            aggregate = ExampleAggregate.__create__()
            aggregate.__save__()

            # Run the process.
            process.run()

            # Check the aggregate has been "moved on".
            self.assertTrue(process.repository[aggregate.id].is_moved_on)

            # Check the __contains__ method of the repo wrapper.
            self.assertIn(aggregate.id, WrappedRepository(process.repository))
            self.assertNotIn(uuid4(), WrappedRepository(process.repository))

            # Check the repository wrapper tracks causal dependencies.
            repository = WrappedRepository(process.repository)
            aggregate = repository[aggregate.id]
            causal_dependencies = repository.causal_dependencies
            self.assertEqual(len(causal_dependencies), 1)
            self.assertEqual((aggregate.id, 1), causal_dependencies[0])

            # Check events from more than one aggregate are stored.
            self.assertIn(aggregate.second_id, process.repository)

    def test_process_application_with_snapshotting(self):
        # Construct example process.
        with ProcessApplicationWithSnapshotting.mixin(self.infrastructure_class)(
            name="test",
            policy=example_policy,
            persist_event_type=ExampleAggregate.Event,
            setup_table=True,
            snapshot_period=2,
        ) as process:
            # Make the process follow itself.
            process.follow("test", process.notification_log)

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

            snapshot_v0 = process.snapshot_strategy.get_snapshot(
                aggregate.id, lt=snapshot.originator_version
            )
            self.assertIsNone(snapshot_v0, Snapshot)

    def test_causal_dependencies(self):
        # Try to process an event that has unresolved causal dependencies.
        pipeline_id1 = 0
        pipeline_id2 = 1

        # Create two events, one has causal dependency on the other.
        process_class = ProcessApplication.mixin(self.infrastructure_class)
        core1 = process_class(
            name="core",
            # persist_event_type=ExampleAggregate.Created,
            persist_event_type=BaseAggregateRoot.Event,
            setup_table=True,
            pipeline_id=pipeline_id1,
        )
        core1.use_causal_dependencies = True

        kwargs = {}
        if self.infrastructure_class.is_constructed_with_session:
            # Needed for SQLAlchemy only.
            kwargs["session"] = core1.session

        core2 = process_class(
            name="core", pipeline_id=pipeline_id2, policy=example_policy, **kwargs
        )
        core2.use_causal_dependencies = True

        # First event in pipeline 1.
        aggregate = ExampleAggregate.__create__()
        aggregate.__save__()

        # Second event in pipeline 2.
        # - it's important this is done in a policy so the causal dependencies are
        # identified
        core2.follow("core", core1.notification_log)
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
        second_entity_records = core1.event_store.record_manager.get_records(
            aggregate.second_id
        )

        self.assertEqual(2, len(aggregate_records))
        self.assertEqual(1, len(second_entity_records))

        self.assertEqual(pipeline_id1, aggregate_records[0].pipeline_id)
        self.assertEqual(pipeline_id2, aggregate_records[1].pipeline_id)
        self.assertEqual(pipeline_id2, second_entity_records[0].pipeline_id)

        # Check the causal dependencies have been constructed.
        # - the first 'Created' event doesn't have an causal dependencies
        self.assertFalse(aggregate_records[0].causal_dependencies)

        # - the second 'Created' event depends on the Created event in another pipeline.
        expect = [{"notification_id": 1, "pipeline_id": pipeline_id1}]
        actual = ObjectJSONDecoder().decode(
            second_entity_records[0].causal_dependencies
        )

        self.assertEqual(expect, actual)

        # - the 'AttributeChanged' event depends on the second Created,
        # which is in the same pipeline, so expect no causal dependencies.
        self.assertFalse(aggregate_records[1].causal_dependencies)

        # Setup downstream process.
        downstream1 = process_class(
            name="downstream",
            pipeline_id=pipeline_id1,
            policy=event_logging_policy,
            **kwargs
        )
        downstream1.follow("core", core1.notification_log)
        downstream2 = process_class(
            name="downstream",
            pipeline_id=pipeline_id2,
            policy=event_logging_policy,
            **kwargs
        )
        downstream2.follow("core", core2.notification_log)

        # Try to process pipeline 2, should fail due to causal dependency.
        with self.assertRaises(CausalDependencyFailed):
            downstream2.run()

        self.assertEqual(
            0,
            len(
                list(downstream1.event_store.record_manager.get_notification_records())
            ),
        )
        self.assertEqual(
            0,
            len(
                list(downstream2.event_store.record_manager.get_notification_records())
            ),
        )

        # Try to process pipeline 1, should work.
        downstream1.run()

        self.assertEqual(
            1,
            len(
                list(downstream1.event_store.record_manager.get_notification_records())
            ),
        )
        self.assertEqual(
            0,
            len(
                list(downstream2.event_store.record_manager.get_notification_records())
            ),
        )

        # Try again to process pipeline 2, should work this time.
        downstream2.run()

        self.assertEqual(
            1,
            len(
                list(downstream1.event_store.record_manager.get_notification_records())
            ),
        )
        self.assertEqual(
            2,
            len(
                list(downstream2.event_store.record_manager.get_notification_records())
            ),
        )

        core1.close()
        core2.close()
        downstream1.close()
        downstream2.close()

    def test_projection_into_custom_orm_obj(self):

        self.define_projection_record_class()

        projection_id = uuid4()

        def projection_policy(repository: WrappedRepository, event):
            if isinstance(event, ExampleAggregate.Created):
                projection = self.projection_record_class(
                    projection_id=projection_id, state=str(event.timestamp)
                )
                repository.save_orm_obj(projection)
            elif isinstance(event, ExampleAggregate.MovedOn):
                projection = self.get_projection_record(
                    projection_record_class=self.projection_record_class,
                    projection_id=projection_id,
                    record_manager=repository.repository.event_store.record_manager,
                )
                assert projection is not None
                repository.delete_orm_obj(projection)

        # Construct example process.
        process_class = ProcessApplication.mixin(self.infrastructure_class)
        with process_class(
            name="test",
            policy=projection_policy,
            persist_event_type=ExampleAggregate.Event,
            setup_table=True,
        ) as process:
            assert isinstance(process, ProcessApplication)

            self.setup_projections_table(process)

            # Make the process follow itself.
            process.follow("test", process.notification_log)

            # Create an aggregate.
            aggregate = ExampleAggregate.__create__()
            aggregate.__save__()

            # Run the process.
            process.run()

            # Check the projection has been created.
            projection = self.get_projection_record(
                projection_record_class=self.projection_record_class,
                projection_id=projection_id,
                record_manager=process.event_store.record_manager,
            )
            self.assertIsInstance(projection, self.projection_record_class)
            self.assertEqual(Decimal(projection.state), aggregate.___created_on__)

            # Move aggregate on.
            aggregate.move_on()
            aggregate.__save__()

            # Run the process.
            process.run()

            # Check the projection has been deleted.
            projection = self.get_projection_record(
                projection_record_class=self.projection_record_class,
                projection_id=projection_id,
                record_manager=process.event_store.record_manager,
            )
            self.assertIsNone(projection)

    def test_cant_follow_self_and_apply_policy_to_generated_events(self):
        with self.assertRaises(ProgrammingError):
            # Construct example process.
            process_class = ProcessApplication.mixin(self.infrastructure_class)
            with process_class(
                name="test",
                policy=None,
                persist_event_type=ExampleAggregate.Event,
                setup_table=True,
                apply_policy_to_generated_events=True,
            ) as process:
                assert isinstance(process, ProcessApplication)

                self.assertTrue(process.apply_policy_to_generated_events)

                # Make the process follow itself.
                process.follow("test", process.notification_log)

    def test_clear_cache_after_exception_recording_event(self):
        # Construct example process.
        process_class = ProcessApplication.mixin(self.infrastructure_class)
        with process_class(
            name="test",
            policy=example_policy,
            persist_event_type=ExampleAggregate.Event,
            setup_table=True,
            use_cache=True,
        ) as process:
            # Check cache is being used.
            self.assertTrue(process.use_cache)

            # Make the process follow itself.
            process.follow("test", process.notification_log)

            # Create an aggregate.
            aggregate = ExampleAggregate.__create__()
            aggregate.__save__()

            # Put aggregate in the cache.
            process.repository._cache[aggregate.id] = aggregate

            # Damage the record manager.
            process.event_store.record_manager.write_records = None

            # Run the process.
            try:
                process.run()
            except Exception:
                pass
            else:
                self.fail("Exception not raised")

            # Check the aggregate is no longer in the cache.
            self.assertNotIn(aggregate.id, process.repository._cache)

    def test_policy_returns_sequence_of_new_aggregates(self):
        def policy(repository, event):
            first = AggregateRoot.__create__(originator_id=(uuid4()))
            second = AggregateRoot.__create__(originator_id=(uuid4()))
            return (first, second)

        # Construct example process.
        process_class = ProcessApplication.mixin(self.infrastructure_class)
        with process_class(
            name="test",
            policy=policy,
            persist_event_type=ExampleAggregate.Event,
            setup_table=True,
            use_cache=True,
        ) as process:
            # Make the process follow itself.
            process.follow("test", process.notification_log)

            # Create an aggregate.
            aggregate = ExampleAggregate.__create__()
            aggregate.__save__()

            # Run the process.
            process.run()

            # Check the two new aggregates are in the cache.
            self.assertEqual(len(process.repository._cache), 2)

            # Check there are three aggregates in the repository.
            ids = process.repository.event_store.record_manager.all_sequence_ids()
            self.assertEqual(len(list(ids)), 3)

    def define_projection_record_class(self):
        class ProjectionRecord(Base):
            __tablename__ = "projections"

            # Projection ID.
            projection_id = Column(UUIDType(), primary_key=True)

            # State of the projection (serialized dict, possibly encrypted).
            state = Column(Text())

        self.projection_record_class = ProjectionRecord

    def setup_projections_table(self, process):
        process.datastore.setup_table(self.projection_record_class)

    def get_projection_record(
        self, projection_record_class, projection_id, record_manager
    ):
        return record_manager.session.query(projection_record_class).get(projection_id)

    def test_handle_prompt_failed(self):
        process = ProcessApplication.mixin(self.infrastructure_class)(
            name="test",
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
                process.publish_prompt_for_events()
        finally:
            unsubscribe(raise_exception)

        subscribe(raise_prompt_failed)
        try:
            with self.assertRaises(PromptFailed):
                process.publish_prompt_for_events()
        finally:
            unsubscribe(raise_prompt_failed)

        try:
            process.publish_prompt_for_events()
        finally:
            process.close()

    def tearDown(self):
        try:
            assert_event_handlers_empty()
        except EventHandlersNotEmptyError:
            clear_event_handlers()
            raise


class TestPromptToPull(TestCase):
    def test_repr(self):
        prompt1 = PromptToPull("process1", pipeline_id=1)
        self.assertEqual(
            repr(prompt1), "PromptToPull(process_name=process1, pipeline_id=1)"
        )

    def test_eq(self):
        prompt1 = PromptToPull("process1", pipeline_id=1)
        prompt2 = PromptToPull("process1", pipeline_id=1)
        prompt3 = PromptToPull("process2", pipeline_id=1)
        prompt4 = PromptToPull("process1", pipeline_id=2)

        self.assertEqual(prompt1, prompt1)
        self.assertEqual(prompt1, prompt2)
        self.assertNotEqual(prompt1, prompt3)
        self.assertNotEqual(prompt1, prompt4)


class TestCommands(TestCase):
    infrastructure_class = SQLAlchemyApplication

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
        commands = CommandProcess.mixin(self.infrastructure_class)(setup_table=True)
        core = ProcessApplication.mixin(self.infrastructure_class)(
            "core", policy=example_policy, session=commands.session
        )

        self.assertFalse(list(commands.event_store.all_events()))

        example_id = uuid4()
        cmd = CreateExample.__create__(example_id=example_id)
        # cmd = Command.__create__(cmd_method='create_example', cmd_args={})
        cmd.__save__()

        domain_events = list(commands.event_store.all_events())
        # self.assertTrue(domain_events)
        self.assertEqual(len(domain_events), 1)

        self.assertFalse(list(core.event_store.all_events()))

        core.follow("commands", commands.notification_log)
        core.run()

        self.assertTrue(list(core.event_store.all_events()))
        self.assertIn(example_id, core.repository)

        # Example shouldn't be "moved on" because core isn't following itself,
        # or applying its policy to generated events.
        self.assertFalse(core.repository[example_id].is_moved_on)

        commands.close()
        core.close()

    def test_apply_policy_to_generated_domain_events(self):
        commands = CommandProcess.mixin(self.infrastructure_class)(setup_table=True)
        core = ProcessApplication.mixin(self.infrastructure_class)(
            name="core",
            policy=example_policy,
            session=commands.session,
            apply_policy_to_generated_events=True,
        )

        with core, commands:
            self.assertFalse(list(commands.event_store.all_events()))

            example_id = uuid4()
            cmd = CreateExample.__create__(example_id=example_id)
            cmd.__save__()

            domain_events = list(commands.event_store.all_events())
            self.assertEqual(len(domain_events), 1)

            self.assertFalse(list(core.event_store.all_events()))

            core.follow("commands", commands.notification_log)
            core.run()

            self.assertTrue(list(core.event_store.all_events()))
            self.assertIn(example_id, core.repository)

            # Example should be "moved on" because core is
            # applying its policy to generated events.
            example = core.repository[example_id]
            self.assertTrue(example.is_moved_on)

            # Check the "second" aggregate exists.
            self.assertIn(example.second_id, core.repository)

    def tearDown(self):
        assert_event_handlers_empty()


# Example aggregate (used in the test).


class ExampleAggregate(BaseAggregateRoot):
    def __init__(self, **kwargs):
        super(ExampleAggregate, self).__init__(**kwargs)
        self.is_moved_on = False
        self.second_id = None

    class Event(BaseAggregateRoot.Event[TEntity]):
        pass

    class Created(Event[TEntity], BaseAggregateRoot.Created[TEntity]):
        pass

    def move_on(self, second_id=None):
        self.__trigger_event__(ExampleAggregate.MovedOn, second_id=second_id)

    class MovedOn(Event[TEntity]):
        @property
        def second_id(self):
            return self.__dict__["second_id"]

        def mutate(self, aggregate):
            assert isinstance(aggregate, ExampleAggregate)
            aggregate.is_moved_on = True
            aggregate.second_id = self.second_id


def example_policy(repository, event):
    if isinstance(event, ExampleAggregate.Created):
        # Create a second aggregate, allowing test to check that
        # events from more than one entity are stored.
        second_id = uuid4()
        second = AggregateRoot.__create__(originator_id=second_id)

        # Get first aggregate and move it on, allowing test to
        # check that the first aggregate was mutated by the policy.
        first = repository[event.originator_id]
        assert isinstance(first, ExampleAggregate)
        first.move_on(second_id=second_id)

        return second

    elif isinstance(event, Command.Created):
        command_class = resolve_topic(event.originator_topic)
        if command_class is CreateExample:
            return ExampleAggregate.__create__(event.example_id)


class LogMessage(BaseAggregateRoot):
    def __init__(self, message="", **kwargs):
        super(LogMessage, self).__init__(**kwargs)
        self.message = message

    class Event(BaseAggregateRoot.Event[TEntity]):
        pass

    class Created(Event[TEntity], BaseAggregateRoot.Created[TEntity]):
        pass


def event_logging_policy(_, event):
    return LogMessage.__create__(uuid4(), message=str(event))


class CreateExample(Command):
    def __init__(self, example_id=None, **kwargs):
        super().__init__(**kwargs)
        self.example_id = example_id


class SaveOrmObject(Command):
    pass


class DeleteOrmObject(Command):
    pass
