import time
from collections import OrderedDict, defaultdict, deque
from decimal import Decimal
from threading import Event, Lock
from types import FunctionType
from typing import (
    Any,
    Deque,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)
from uuid import UUID

from eventsourcing.application.notificationlog import (
    AbstractNotificationLog,
    NotificationLogReader,
)
from eventsourcing.application.simple import SimpleApplication
from eventsourcing.application.snapshotting import SnapshottingApplication
from eventsourcing.domain.model.aggregate import (
    BaseAggregateRoot,
    TAggregate,
    TAggregateEvent,
)
from eventsourcing.domain.model.entity import TDomainEvent
from eventsourcing.domain.model.events import publish, subscribe, unsubscribe
from eventsourcing.exceptions import (
    CausalDependencyFailed,
    ProgrammingError,
    PromptFailed,
)
from eventsourcing.infrastructure.base import ACIDRecordManager, TrackingKwargs
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.whitehead import ActualOccasion, IterableOfEvents

ListOfAggregateEvents = List[TAggregateEvent]
CausalDependencies = Dict[str, int]
ListOfCausalDependencies = List[CausalDependencies]


class ProcessEvent(ActualOccasion, Generic[TDomainEvent]):
    def __init__(
        self,
        domain_events: Iterable[TDomainEvent],
        tracking_kwargs: Optional[TrackingKwargs] = None,
        causal_dependencies: Optional[ListOfCausalDependencies] = None,
        orm_objs_pending_save: Sequence[Any] = (),
        orm_objs_pending_delete: Sequence[Any] = (),
    ):
        self.domain_events = domain_events
        self.tracking_kwargs = tracking_kwargs
        self.causal_dependencies = causal_dependencies
        self.orm_objs_pending_save = orm_objs_pending_save
        self.orm_objs_pending_delete = orm_objs_pending_delete


class Prompt(ActualOccasion):
    pass


def is_prompt(events: IterableOfEvents) -> bool:
    return (
        isinstance(events, list)
        and len(events) == 1
        and isinstance(events[0], PromptToPull)
    )


class PromptToPull(Prompt):
    def __init__(self, process_name: str, pipeline_id: int):
        self.process_name: str = process_name
        self.pipeline_id: int = pipeline_id

    def __eq__(self, other: object) -> bool:
        return bool(
            other
            and isinstance(other, type(self))
            and self.process_name == other.process_name
            and self.pipeline_id == other.pipeline_id
        )

    def __repr__(self) -> str:
        return "{}({}={}, {}={})".format(
            type(self).__name__,
            "process_name",
            self.process_name,
            "pipeline_id",
            self.pipeline_id,
        )


class PromptToQuit(Prompt):
    pass


class WrappedRepository(Generic[TAggregate, TAggregateEvent]):
    """
    Used to wrap an event sourced repository for use in process application
    policy so that use of, and changes to, domain model aggregates can be
    automatically detected and recorded.

    Implements a "dictionary like" interface, so that aggregates can be
    accessed by ID.
    """

    def __init__(
        self, repository: EventSourcedRepository[TAggregate, TAggregateEvent]
    ) -> None:
        self.repository = repository
        self.retrieved_aggregates: Dict[UUID, TAggregate] = {}
        self.causal_dependencies: List[Tuple[UUID, int]] = []
        self.orm_objs_pending_save: List[Any] = []
        self.orm_objs_pending_delete: List[Any] = []

    def __getitem__(self, entity_id: UUID) -> TAggregate:
        try:
            aggregate = self.retrieved_aggregates[entity_id]
        except KeyError:
            aggregate = self.repository.__getitem__(entity_id)
            self.retrieved_aggregates[entity_id] = aggregate
            self.causal_dependencies.append((aggregate.id, aggregate.__version__))
        return aggregate

    def __contains__(self, entity_id: UUID) -> bool:
        return self.repository.__contains__(entity_id)

    def save_orm_obj(self, orm_obj: Any) -> None:
        """
        Includes orm_obj in "process event", so that projections into
        custom ORM objects is as reliable with respect to sudden restarts
        as "normal" domain event processing in a process application.
        """
        self.orm_objs_pending_save.append(orm_obj)

    def delete_orm_obj(self, orm_obj: Any) -> None:
        """
        Includes orm_obj in "process event", so that projections into
        custom ORM objects is as reliable with respect to sudden restarts
        as "normal" domain event processing in a process application.
        """
        self.orm_objs_pending_delete.append(orm_obj)


class ProcessApplication(SimpleApplication[TAggregate, TAggregateEvent]):
    set_notification_ids = False
    use_causal_dependencies = False
    notification_log_reader_class = NotificationLogReader
    apply_policy_to_generated_events = False

    def __init__(
        self,
        name: str = "",
        policy: Optional[FunctionType] = None,
        setup_table: bool = False,
        use_direct_query_if_available: bool = False,
        notification_log_reader_class: Optional[Type[NotificationLogReader]] = None,
        apply_policy_to_generated_events: bool = False,
        **kwargs: Any
    ):
        self.policy_func = policy
        self.readers: OrderedDict[str, NotificationLogReader] = OrderedDict()
        self.is_reader_position_ok: Dict[str, bool] = defaultdict(bool)
        self._notification_generators: Dict[str, Iterator[Dict[str, Any]]] = {}
        self._policy_lock = Lock()
        self.clock_event: Optional[Event] = None
        self.tick_interval: Optional[Union[float, int]] = None
        self.use_direct_query_if_available = use_direct_query_if_available
        self.notification_log_reader_class = (
            notification_log_reader_class or type(self).notification_log_reader_class
        )
        self.apply_policy_to_generated_events = (
            apply_policy_to_generated_events
            or type(self).apply_policy_to_generated_events
        )

        super(ProcessApplication, self).__init__(
            name=name, setup_table=setup_table, **kwargs
        )

        if self._event_store:
            self.notification_topic_key = (
                self._event_store.record_manager.field_names.topic
            )
            self.notification_state_key = (
                self._event_store.record_manager.field_names.state
            )

        # Publish prompts for any domain events that we persist.
        #  - this means when a process application is used as a simple
        #    application, with calls to aggregate __save__() methods,
        #    then the new events that are stored might need to be processed
        #    by another application. So it can help also to publish a
        #    prompt after the events have been stored so that followers
        #    can be immediately nudged to process the events (otherwise they
        #    would only pick up the events next time they happen to run).
        #    The particular way a prompt published here is actually sent to
        #    any followers is the responsibility of a particular system runner.
        if self._persistence_policy:
            subscribe(
                predicate=self._persistence_policy.is_event, handler=self.publish_prompt
            )

    def close(self) -> None:
        if self._persistence_policy:
            unsubscribe(
                predicate=self._persistence_policy.is_event, handler=self.publish_prompt
            )
        super(ProcessApplication, self).close()

    def publish_prompt(self, _: Optional[IterableOfEvents] = None) -> None:
        """
        Publishes prompt for a given event.

        Used to prompt downstream process application when an event
        is published by this application's model, which can happen
        when application command methods, rather than the process policy,
        are called.

        Wraps exceptions with PromptFailed, to avoid application policy exceptions being
        seen directly in other applications when running synchronously in single thread.
        """

        prompt = PromptToPull(self.name, self.pipeline_id)
        try:
            publish([prompt])
        except PromptFailed:
            raise
        except Exception as e:
            raise PromptFailed("{}: {}".format(type(e), str(e)))

    def follow(
        self, upstream_application_name: str, notification_log: AbstractNotificationLog
    ) -> None:
        if (
            upstream_application_name == self.name
            and self.apply_policy_to_generated_events
        ):
            raise ProgrammingError(
                "Process application not allowed to follow itself because "
                "its 'apply_policy_to_generated_events' attribute is True."
            )

        # Create a reader.
        reader = self.notification_log_reader_class(
            notification_log,
            use_direct_query_if_available=self.use_direct_query_if_available,
        )
        self.readers[upstream_application_name] = reader

    def run(
        self, prompt: Optional[Prompt] = None, advance_by: Optional[int] = None
    ) -> int:

        if prompt:
            assert isinstance(prompt, PromptToPull)
            upstream_names = [prompt.process_name]
        else:
            upstream_names = list(self.readers.keys())

        notification_count = 0

        record_manager = self.event_store.record_manager
        assert isinstance(record_manager, ACIDRecordManager)

        for upstream_name in upstream_names:

            if not self.is_reader_position_ok[upstream_name]:
                self.del_notification_generator(upstream_name)
                self.set_reader_position_from_tracking_records(upstream_name)
                self.is_reader_position_ok[upstream_name] = True

            while True:
                with self._policy_lock:
                    # Get notification generator.
                    generator = self.get_notification_generator(
                        upstream_name, advance_by
                    )
                    try:
                        notification = next(generator)
                    except StopIteration:
                        self.del_notification_generator(upstream_name)
                        break

                    notification_count += 1

                    # Get domain event from notification.
                    event = self.get_event_from_notification(notification)

                    # Decode causal dependencies of the domain event notification.
                    causal_dependencies_json = notification.get("causal_dependencies")
                    if causal_dependencies_json:
                        causal_dependencies = self.event_store.event_mapper.json_loads(
                            causal_dependencies_json
                        )
                    else:
                        causal_dependencies = []

                    # Check causal dependencies are satisfied.
                    for causal_dependency in causal_dependencies:
                        # Todo: Check causal dependency on system software version?

                        # Check causal dependencies on event notifications.
                        assert isinstance(causal_dependency, dict)
                        pipeline_id = causal_dependency["pipeline_id"]
                        notification_id = causal_dependency["notification_id"]

                        has_tracking_record = record_manager.has_tracking_record(
                            upstream_application_name=upstream_name,
                            pipeline_id=pipeline_id,
                            notification_id=notification_id,
                        )
                        if not has_tracking_record:
                            # Invalidate reader position.
                            self.is_reader_position_ok[upstream_name] = False

                            # Raise exception.
                            raise CausalDependencyFailed(
                                {
                                    "application_name": self.name,
                                    "upstream_name": upstream_name,
                                    "pipeline_id": pipeline_id,
                                    "notification_id": notification_id,
                                }
                            )

                    # Wait on the clock event, if there is one.
                    if self.clock_event is not None:
                        self.clock_event.wait()

                    # Process upstream event.
                    new_events: Sequence[TAggregateEvent] = self.process_upstream_event(
                        event, notification["id"], upstream_name
                    )

                self.take_snapshots(new_events)

                # Publish a prompt if there are new notifications.
                # Todo: Optionally send events as prompts, saves pulling
                #  event if it arrives in order.
                if any([event.__notifiable__ for event in new_events]):
                    self.publish_prompt()

        return notification_count

    def process_upstream_event(
        self, domain_event: TAggregateEvent, notification_id: int, upstream_name: str
    ) -> ListOfAggregateEvents:
        cycle_started: Optional[float] = None
        if self.tick_interval is not None:
            cycle_started = time.process_time()

        # Call policy with the upstream event.
        (
            domain_events,
            causal_dependencies,
            orm_objs_pending_save,
            orm_objs_pending_delete,
        ) = self.call_policy(domain_event)

        # Todo: Supplement causal dependencies with system software version?
        #  - this may help to inhibit premature processing when upgrading

        # Todo: Optionally add correlation and causation IDs here. Could be done
        #  in user application code, perhaps with a decorator on policy functions
        #  but having it done here would be more convenient.

        # Todo: Optionally add event and system version numbers in events. This
        #  would help with upcasting them. Could be done in user application code,
        #  with either aggregate or event base class, but having it done here would
        #  be more convenient.

        # Record process event.
        try:
            tracking_kwargs = self.construct_tracking_kwargs(
                notification_id, upstream_name
            )
            process_event = ProcessEvent(
                domain_events=domain_events,
                tracking_kwargs=tracking_kwargs,
                causal_dependencies=causal_dependencies,
                orm_objs_pending_save=orm_objs_pending_save,
                orm_objs_pending_delete=orm_objs_pending_delete,
            )
            self.record_process_event(process_event)

            # Todo: Maybe write one tracking record at the end of a run, if
            #  necessary, or only during a period of time when nothing happens?
        except Exception as exc:
            # Need to invalidate reader position, so it is refreshed.
            self.is_reader_position_ok[upstream_name] = False

            # Need to purge from the cache relevant entities that
            # have evolved their state past what has been recorded,
            # otherwise strange errors (about version mismatches, or
            # when identifying causal dependencies) can arise.
            if self.repository._cache:
                originator_ids = set([event.originator_id for event in domain_events])
                for originator_id in originator_ids:
                    self.repository._cache.pop(originator_id, None)
            raise exc
        else:
            if self.tick_interval is not None:
                assert cycle_started
                # Todo: Change this to use the full cycle time
                #  (improve getting notifications first).
                cycle_ended = time.process_time()
                cycle_time = cycle_ended - cycle_started
                cycle_perc = 100 * (cycle_time) / self.tick_interval
                if cycle_perc > 100:
                    msg = "Warning: {} cycle exceeded tick interval by: {:.2f}%".format(
                        self.name, cycle_perc - 100
                    )
                    print(msg)
        return domain_events

    def get_event_from_notification(
        self, notification: Dict[str, Any]
    ) -> TAggregateEvent:
        return self.event_store.event_mapper.event_from_topic_and_state(
            topic=notification[self.notification_topic_key],
            state=notification[self.notification_state_key],
        )

    def get_notification_generator(
        self, upstream_name: str, advance_by: Optional[int]
    ) -> Iterator[Dict[str, Any]]:
        # Dict avoids re-entrant calls to run() starting their own generator,
        # so that notifications are only received once. Was needed in
        # single-threaded runner before it was changed to use iteration not
        # recursion. Hence, probably no longer needed - use reader directly.
        try:
            generator = self._notification_generators[upstream_name]
        except KeyError:
            # Todo: Rename as 'iterator'? We use an iterator, doesn't matter
            #  whether or not it is a generator.
            generator = self.read_reader(upstream_name, advance_by)
            self._notification_generators[upstream_name] = generator
        return generator

    def read_reader(
        self, upstream_name: str, advance_by: Optional[int] = None
    ) -> Iterator[Dict[str, Any]]:
        return self.readers[upstream_name].read(advance_by=advance_by)

    def del_notification_generator(self, upstream_name: str) -> None:
        try:
            del self._notification_generators[upstream_name]
        except KeyError:
            pass

    def take_snapshots(self, new_events: Sequence[TAggregateEvent]) -> None:
        pass

    def set_reader_position_from_tracking_records(self, upstream_name: str) -> None:
        reader = self.readers[upstream_name]
        record_manager = self.event_store.record_manager
        assert isinstance(record_manager, ACIDRecordManager)
        recorded_position = record_manager.get_max_tracking_record_id(upstream_name)
        reader.seek(recorded_position)

    def call_policy(
        self, domain_event: TAggregateEvent
    ) -> Tuple[ListOfAggregateEvents, ListOfCausalDependencies, List[Any], List[Any]]:
        # Get the application policy.
        policy = self.policy_func or self.policy

        # Wrap the actual repository, so we can collect aggregates.
        repository = WrappedRepository(self.repository)

        # Initialise a deque for FIFO queue of unprocessed events.
        unprocessed: Deque[TAggregateEvent] = deque()
        unprocessed.append(domain_event)

        # Initialise a list to collect and return all the generated events.
        all_generated: ListOfAggregateEvents[TAggregateEvent] = []

        # Iterate on the FIFO queue of unprocessed events.
        while len(unprocessed):

            # Get the next unprocessed domain event.
            domain_event = unprocessed.popleft()

            # Call the policy with this domain event.
            returned = policy(repository, domain_event)

            # Collect aggregates retrieved by the policy.
            touched = list(repository.retrieved_aggregates.values())

            if returned is not None:
                # Convert returned item to list, if necessary.
                if isinstance(returned, Sequence):
                    new_aggregates = returned
                else:
                    new_aggregates = [returned]

                for aggregate in new_aggregates:
                    # Put new aggregates in repository cache (avoids replay).
                    if repository.repository.use_cache:
                        repository.repository._cache[aggregate.id] = aggregate

                    # Make new aggregates available in subsequent policy calls.
                    if self.apply_policy_to_generated_events:
                        repository.retrieved_aggregates[aggregate.id] = aggregate

                # Extend the list of touched aggregates with
                # the new ones returned from the policy.
                touched.extend(new_aggregates)

            # Collect all the new_events events.
            new_events: ListOfAggregateEvents = self.collect_pending_events(touched)

            # Extend the list of new_events events.
            all_generated.extend(new_events)

            # Enqueue the new events for subsequence processing.
            if self.apply_policy_to_generated_events:
                unprocessed.extend(new_events)

        # Translate causal dependencies from version of entity to position in pipeline.
        causal_dependencies: ListOfCausalDependencies = []
        if self.use_causal_dependencies:
            # Todo: Optionally reference causal dependencies in current pipeline
            #  and then support processing notification from a single pipeline in
            #  parallel, according to dependencies.
            highest: Dict[int, int] = defaultdict(int)
            rm = self.event_store.record_manager
            assert isinstance(rm, ACIDRecordManager)
            for entity_id, entity_version in repository.causal_dependencies:
                pipeline_id, notification_id = rm.get_pipeline_and_notification_id(
                    entity_id, entity_version
                )
                if pipeline_id is not None and pipeline_id != self.pipeline_id:
                    highest[pipeline_id] = max(notification_id, highest[pipeline_id])

            for pipeline_id, notification_id in highest.items():
                causal_dependencies.append(
                    {"pipeline_id": pipeline_id, "notification_id": notification_id}
                )

        return (
            all_generated,
            causal_dependencies,
            repository.orm_objs_pending_save,
            repository.orm_objs_pending_delete,
        )

    def policy(
        self,
        repository: WrappedRepository[TAggregate, TAggregateEvent],
        event: TAggregateEvent,
    ) -> Optional[Union[TAggregate, Sequence[TAggregate]]]:
        """
        Empty method, can be overridden in subclasses to implement concrete policy.
        """

    def collect_pending_events(
        self, aggregates: Sequence[TAggregate]
    ) -> ListOfAggregateEvents:
        pending_events: ListOfAggregateEvents = []
        num_changed_aggregates = 0
        # This doesn't necessarily obtain events in causal order...
        for aggregate in aggregates:
            batch = aggregate.__batch_pending_events__()
            if len(batch):
                num_changed_aggregates += 1
            pending_events += batch

        # ...so sort pending events across all aggregates.
        if num_changed_aggregates > 1:
            # Sort the events by timestamp.
            #  - this method is intended to establish the correct
            #    causal ordering of all these new events across all aggregates. It
            #    should work if all events are timestamped, all their timestamps
            #    are from the same clock, and none have the same value. If this
            #    doesn't work properly, for some reason, it would be possible when
            #    several aggregates publish events that depend on each other that
            #    concatenating pending events taken from each in turn will be incorrect
            #    and could potentially cause processing errors in a downstream process
            #    application that depends on the correct causal ordering of events. In
            #    the worst case, the events will still be placed correctly in the
            #    aggregate sequence, but if timestamps are skewed and so do not
            #    correctly order the events, the events may be out of order in their
            #    notification log. It is expected in normal usage that these events
            #    are created in the same operating system thread, with timestamps
            #    from the same operating system clock, and so the timestamps will
            #    provide the correct order. However, if somehow different events are
            #    timestamped from different clocks, then problems may occur if those
            #    clocks give timestamps that skew the correct causal order.

            def pick_timestamp(event: BaseAggregateRoot.Event) -> Decimal:
                return event.timestamp

            pending_events.sort(key=pick_timestamp)

        return pending_events

    def construct_tracking_kwargs(
        self, notification_id: int, upstream_application_name: str
    ) -> TrackingKwargs:
        return {
            "application_name": self.name,
            "upstream_application_name": upstream_application_name,
            "pipeline_id": self.pipeline_id,
            "notification_id": notification_id,
        }

    def record_process_event(self, process_event: ProcessEvent) -> None:
        # Construct event records.
        event_records = self.construct_event_records(
            process_event.domain_events, process_event.causal_dependencies
        )

        # Write event records with tracking record.
        record_manager = self.event_store.record_manager
        assert isinstance(record_manager, ACIDRecordManager)
        record_manager.write_records(
            records=event_records,
            tracking_kwargs=process_event.tracking_kwargs,
            orm_objs_pending_save=process_event.orm_objs_pending_save,
            orm_objs_pending_delete=process_event.orm_objs_pending_delete,
        )

    def construct_event_records(
        self,
        pending_events: Iterable[TAggregateEvent],
        causal_dependencies: Optional[ListOfCausalDependencies],
    ) -> List:
        # Convert to event records.
        sequenced_items = self.event_store.items_from_events(pending_events)
        record_manager = self.event_store.record_manager
        assert record_manager
        assert isinstance(record_manager, ACIDRecordManager)
        event_records = list(record_manager.to_records(sequenced_items))

        # Set notification log IDs, and causal dependencies.
        if len(event_records):
            # Todo: Maybe keep track of what this probably is, to
            #  avoid query. Like log reader, invalidate on error.
            if self.set_notification_ids:
                notification_id_name = record_manager.notification_id_name
                current_max = record_manager.get_max_notification_id()
                for domain_event, event_record in zip(pending_events, event_records):
                    if type(domain_event).__notifiable__:
                        current_max += 1
                        setattr(event_record, notification_id_name, current_max)
                    else:
                        setattr(
                            event_record, notification_id_name, "event-not-notifiable"
                        )

            if self.use_causal_dependencies:
                assert hasattr(record_manager.record_class, "causal_dependencies")
                causal_dependencies_json = self.event_store.event_mapper.json_dumps(
                    causal_dependencies
                ).decode('utf8')
                # Only need first event to carry the dependencies.
                event_records[0].causal_dependencies = causal_dependencies_json

        return event_records

    def setup_table(self) -> None:
        super(ProcessApplication, self).setup_table()
        if self._datastore is not None:
            record_manager = self.event_store.record_manager
            assert isinstance(record_manager, ACIDRecordManager)
            self._datastore.setup_table(record_manager.tracking_record_class)

    def drop_table(self) -> None:
        super(ProcessApplication, self).drop_table()
        if self.datastore is not None:
            record_manager = self.event_store.record_manager
            assert isinstance(record_manager, ACIDRecordManager)
            self.datastore.drop_table(record_manager.tracking_record_class)


class ProcessApplicationWithSnapshotting(SnapshottingApplication, ProcessApplication):
    def take_snapshots(self, new_events: Sequence[TAggregateEvent]) -> None:
        assert self.snapshotting_policy
        for event in new_events:
            if self.snapshotting_policy.condition([event]):
                self.snapshotting_policy.take_snapshot([event])
