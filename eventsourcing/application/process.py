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
from eventsourcing.application.simple import (
    ListOfCausalDependencies,
    ProcessEvent,
    Prompt,
    PromptToPull,
    SimpleApplication,
)
from eventsourcing.application.snapshotting import SnapshottingApplication
from eventsourcing.domain.model.aggregate import (
    BaseAggregateRoot,
    TAggregate,
    TAggregateEvent,
)
from eventsourcing.domain.model.events import subscribe, unsubscribe
from eventsourcing.exceptions import CausalDependencyFailed, ProgrammingError
from eventsourcing.infrastructure.base import RecordManagerWithTracking, TrackingKwargs
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.whitehead import IterableOfEvents

ListOfAggregateEvents = List[TAggregateEvent]


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
                predicate=self._persistence_policy.is_event,
                handler=self.publish_prompt_for_events,
            )

    def close(self) -> None:
        if self._persistence_policy:
            unsubscribe(
                predicate=self._persistence_policy.is_event,
                handler=self.publish_prompt_for_events,
            )
        super(ProcessApplication, self).close()

    def publish_prompt_for_events(self, _: Optional[IterableOfEvents] = None) -> None:
        """
        Publishes prompt for a given event.

        Used to prompt downstream process application when an event
        is published by this application's model, which can happen
        when application command methods, rather than the process policy,
        are called.

        Wraps exceptions with PromptFailed, to avoid application policy exceptions being
        seen directly in other applications when running synchronously in single thread.
        """

        self.publish_prompt()

    def follow(
        self, upstream_application_name: str, notification_log: AbstractNotificationLog
    ) -> None:
        """
        Sets up process application to follow the given notification log of an
        upstream application.

        :param upstream_application_name: Name of the upstream application.
        :param notification_log: Notification log that will be processed.
        """
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
        """
        Pulls event notifications from notification logs being followed by
        this process application, and processes the contained domain events.

        :param prompt: Optional prompt, specifying a particular notification log.
        :param advance_by: Maximum event notifications to process.
        :return: Returns number of events that have been processed.
        """

        if prompt:
            assert isinstance(prompt, PromptToPull)
            upstream_names = [prompt.process_name]
        else:
            upstream_names = list(self.readers.keys())

        notification_count = 0

        for upstream_name in upstream_names:

            # Set reader position, if necessary.
            if not self.is_reader_position_ok[upstream_name]:
                self.del_notification_generator(upstream_name)
                self.set_reader_position_from_tracking_records(upstream_name)
                self.is_reader_position_ok[upstream_name] = True

            try:
                # Process all the new event notifications in the reader.
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

                        # Increment the notification count.
                        notification_count += 1

                        # Check causal dependencies.
                        self.check_causal_dependencies(
                            upstream_name, notification.get("causal_dependencies")
                        )

                        # Get event from notification.
                        event = self.get_event_from_notification(notification)

                        # Wait for the clock, if there is one.
                        if self.clock_event is not None:
                            self.clock_event.wait()

                        # Process domain event.
                        new_events, new_records = self.process_upstream_event(
                            event, notification["id"], upstream_name
                        )

                    self.take_snapshots(new_events)

                    # Publish a prompt if there are new notifications.
                    # Todo: Optionally send events as prompts, saves pulling
                    #  event if it arrives in order.
                    if any([event.__notifiable__ for event in new_events]):
                        self.publish_prompt()
            except Exception as e:
                # Need to invalidate reader position, so it is refreshed.
                self.is_reader_position_ok[upstream_name] = False
                raise

        return notification_count

    def check_causal_dependencies(self, upstream_name, causal_dependencies_json):
        """
        Checks the causal dependencies are satisfied (have already been processed).

        :param upstream_name: Name of the upstream application being processed.
        :param causal_dependencies_json: Pipelines and positions in notification logs.
        :raises CausalDependencyFailed: If causal dependencies are not satisfied.
        """
        # Decode causal dependencies of the domain event notification.
        if causal_dependencies_json:
            causal_dependencies = self.event_store.event_mapper.json_loads(
                causal_dependencies_json
            )
        else:
            causal_dependencies = []

        record_manager = self.event_store.record_manager
        assert isinstance(record_manager, RecordManagerWithTracking)

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

    def process_upstream_event(
        self, domain_event: TAggregateEvent, notification_id: int, upstream_name: str
    ) -> Tuple[ListOfAggregateEvents, List]:
        """
        Processes given domain event from an upstream notification log.

        Calls the process application policy, and then records a process event,
        hence recording atomically all new domain events created by the call
        to the policy along with any ORM objects that may result.

        :param domain_event: Domain event to be processed.
        :param notification_id: Position in notification log.
        :param upstream_name: Name of upstream application.
        :return: Returns a list of new domain events.
        """
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
            new_event_records = self.record_process_event(process_event)

            # Todo: Maybe write one tracking record at the end of a run, if
            #  necessary, or only during a period of time when nothing happens?
        except Exception as exc:
            # Need to purge from the cache relevant entities that
            # have evolved their state past what has been recorded,
            # otherwise strange errors (about version mismatches, or
            # when identifying causal dependencies) can arise.
            if self.repository.use_cache:
                originator_ids = set([event.originator_id for event in domain_events])
                with self.repository.cache_lock:
                    for originator_id in originator_ids:
                        self.repository.cache.pop(originator_id, None)
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
        return domain_events, new_event_records

    def get_event_from_notification(
        self, notification: Dict[str, Any]
    ) -> TAggregateEvent:
        """
        Extracts the domain event of an event notification.

        :param notification: The event notification.
        :return: A domain event.
        """
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
        recorded_position = self.get_recorded_position(upstream_name)
        reader.seek(recorded_position)

    def get_recorded_position(self, upstream_name):
        record_manager = self.event_store.record_manager
        assert isinstance(record_manager, RecordManagerWithTracking)
        recorded_position = record_manager.get_max_tracking_record_id(upstream_name)
        return recorded_position

    def call_policy(
        self, domain_event: TAggregateEvent
    ) -> Tuple[ListOfAggregateEvents, ListOfCausalDependencies, List[Any], List[Any]]:
        """
        Calls the process application policy with the given domain event.

        :param domain_event: Domain event that will be given to the policy.

        :return: Returns a list of domain events, and a list of causal dependencies.
        """
        # Get the application policy.
        policy = self.policy_func or self.policy

        # Wrap the actual repository, so we can collect aggregates.
        wrappedrepo = WrappedRepository(self.repository)

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
            returned = policy(wrappedrepo, domain_event)

            # Collect aggregates retrieved by the policy.
            touched = list(wrappedrepo.retrieved_aggregates.values())

            if returned is not None:
                # Convert returned item to list, if necessary.
                if isinstance(returned, Sequence):
                    new_aggregates = returned
                else:
                    new_aggregates = [returned]

                for aggregate in new_aggregates:
                    # Put new aggregates in repository cache (avoids replay).
                    if wrappedrepo.repository.use_cache:
                        wrappedrepo.repository.put_entity_in_cache(
                            aggregate.id, aggregate
                        )

                    # Make new aggregates available in subsequent policy calls.
                    if self.apply_policy_to_generated_events:
                        wrappedrepo.retrieved_aggregates[aggregate.id] = aggregate

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
            assert isinstance(rm, RecordManagerWithTracking)
            for entity_id, entity_version in wrappedrepo.causal_dependencies:
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
            wrappedrepo.orm_objs_pending_save,
            wrappedrepo.orm_objs_pending_delete,
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
        """
        Collects all the pending events from the given sequence of aggregates.

        :param aggregates: Sequence of aggregates.
        :return: Returns a list of domain events.
        """
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

    def setup_table(self) -> None:
        super(ProcessApplication, self).setup_table()
        if self._datastore is not None:
            record_manager = self.event_store.record_manager
            assert isinstance(record_manager, RecordManagerWithTracking)
            self._datastore.setup_table(record_manager.tracking_record_class)

    def drop_table(self) -> None:
        super(ProcessApplication, self).drop_table()
        if self.datastore is not None:
            record_manager = self.event_store.record_manager
            assert isinstance(record_manager, RecordManagerWithTracking)
            self.datastore.drop_table(record_manager.tracking_record_class)


class ProcessApplicationWithSnapshotting(SnapshottingApplication, ProcessApplication):
    """
    Supplements process applications that will use snapshotting.
    """
    def take_snapshots(self, new_events: Sequence[TAggregateEvent]) -> None:
        """
        Takes snapshot of aggregates, according to the policy.

        :param new_events: Domain events used to detect if a snapshot is to be taken.
        """
        assert self.snapshotting_policy
        for event in new_events:
            if self.snapshotting_policy.condition([event]):
                self.snapshotting_policy.take_snapshot([event])
