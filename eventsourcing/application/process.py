import time
from collections import OrderedDict, defaultdict
from threading import Lock

from eventsourcing.application.pipeline import Pipeable
from eventsourcing.application.simple import SimpleApplication
from eventsourcing.application.snapshotting import SnapshottingApplication
from eventsourcing.domain.model.events import publish, subscribe, unsubscribe
from eventsourcing.exceptions import CausalDependencyFailed, PromptFailed
from eventsourcing.infrastructure.base import ACIDRecordManager
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.interface.notificationlog import NotificationLogReader
from eventsourcing.utils.transcoding import json_dumps, json_loads


class ProcessEvent(object):
    def __init__(self, new_events, tracking_kwargs=None, causal_dependencies=None):
        self.new_events = new_events
        self.tracking_kwargs = tracking_kwargs
        self.causal_dependencies = causal_dependencies


class ProcessApplication(Pipeable, SimpleApplication):
    set_notification_ids = False
    use_causal_dependencies = False

    def __init__(self, name=None, policy=None, setup_table=False, **kwargs):
        self.policy_func = policy
        self.readers = OrderedDict()
        self.is_reader_position_ok = defaultdict(bool)
        self._notification_generators = {}
        self._policy_lock = Lock()
        self.clock_event = None
        self.tick_interval = None
        super(ProcessApplication, self).__init__(name=name, setup_table=setup_table, **kwargs)

        # Publish prompts for any domain events that we persist.
        if self.persistence_policy:
            subscribe(
                predicate=self.persistence_policy.is_event,
                handler=self.publish_prompt,
            )

    def close(self):
        if self.persistence_policy:
            unsubscribe(
                predicate=self.persistence_policy.is_event,
                handler=self.publish_prompt,
            )
        super(ProcessApplication, self).close()

    def publish_prompt(self, event=None):
        """
        Publishes prompt for a given event.

        Used to prompt downstream process application when an event
        is published by this application's model, which can happen
        when application command methods, rather than the process policy,
        are called.

        Wraps exceptions with PromptFailed, to avoid application policy exceptions being
        seen directly in other applications when running synchronously in single thread.
        """

        prompt = Prompt(self.name, self.pipeline_id)
        try:
            publish(prompt)
        except PromptFailed:
            raise
        except Exception as e:
            raise PromptFailed("{}: {}".format(type(e), str(e)))

    def follow(self, upstream_application_name, notification_log):
        # Create a reader.
        reader = NotificationLogReader(notification_log, use_direct_query_if_available=True)
        self.readers[upstream_application_name] = reader

    def run(self, prompt=None, advance_by=None):

        if prompt:
            assert isinstance(prompt, Prompt)
            upstream_names = [prompt.process_name]
        else:
            upstream_names = self.readers.keys()

        notification_count = 0
        for upstream_name in upstream_names:

            if not self.is_reader_position_ok[upstream_name]:
                self.del_notification_generator(upstream_name)
                self.set_reader_position_from_tracking_records(upstream_name)
                self.is_reader_position_ok[upstream_name] = True

            while True:
                with self._policy_lock:
                    # Get notification generator.
                    generator = self.get_notification_generator(upstream_name, advance_by)
                    try:
                        notification = next(generator)
                    except StopIteration:
                        self.del_notification_generator(upstream_name)
                        break

                    notification_count += 1

                    # Get domain event from notification.
                    event = self.get_event_from_notification(notification)

                    # Decode causal dependencies of the domain event.
                    causal_dependencies = notification.get('causal_dependencies') or '[]'
                    causal_dependencies = json_loads(causal_dependencies) or []

                    # Check causal dependencies are satisfied.
                    for causal_dependency in causal_dependencies:
                        pipeline_id = causal_dependency['pipeline_id']
                        notification_id = causal_dependency['notification_id']

                        _manager = self.event_store.record_manager
                        has_tracking_record = _manager.has_tracking_record(
                            upstream_application_name=upstream_name,
                            pipeline_id=pipeline_id,
                            notification_id=notification_id
                        )
                        if not has_tracking_record:
                            # Invalidate reader position.
                            self.is_reader_position_ok[upstream_name] = False

                            # Raise exception.
                            raise CausalDependencyFailed({
                                'application_name': self.name,
                                'upstream_name': upstream_name,
                                'pipeline_id': pipeline_id,
                                'notification_id': notification_id
                            })

                    # Wait on the clock event, if there is one.
                    if self.clock_event is not None:
                        self.clock_event.wait()

                    # print("Processing upstream event: ", event)
                    new_events = self.process_upstream_event(event, notification['id'], upstream_name)

                self.take_snapshots(new_events)

                # Publish a prompt if there are new notifications.
                # Todo: Optionally send events as prompts, saves pulling event if it arrives in order.
                if any([event.__notifiable__ for event in new_events]):
                    self.publish_prompt()

        return notification_count

    def process_upstream_event(self, event, notification_id, upstream_name):
        if self.tick_interval is not None:
            cycle_started = time.process_time()
        else:
            cycle_started = None
        # Call policy with the upstream event.
        all_aggregates, causal_dependencies = self.call_policy(event)
        # Collect pending events.
        new_events = self.collect_pending_events(all_aggregates)
        # Record process event.
        try:
            tracking_kwargs = self.construct_tracking_kwargs(
                notification_id, upstream_name
            )
            process_event = ProcessEvent(
                new_events, tracking_kwargs, causal_dependencies
            )
            self.record_process_event(process_event)

            # Todo: Maybe write one tracking record at the end of a run, if
            # necessary, or only during a period of time when nothing happens?
        except Exception as exc:
            # Need to invalidate reader position, so it is refreshed.
            self.is_reader_position_ok[upstream_name] = False

            # Need to purge from the cache relevant entities that
            # have evolved their state past what has been recorded,
            # otherwise strange errors (about version mismatches, or
            # when identifying causal dependencies) can arise.
            if self.repository._cache:
                originator_ids = set([event.originator_id for event in new_events])
                for originator_id in originator_ids:
                    try:
                        del self.repository._cache[originator_id]
                    except KeyError:
                        pass
            raise exc
        else:
            if self.tick_interval is not None:
                # Todo: Change this to use the full cycle time (improve getting notifications first).
                cycle_ended = time.process_time()
                cycle_time = cycle_ended - cycle_started
                cycle_perc = 100 * (cycle_time) / self.tick_interval
                if cycle_perc > 100:
                    msg = f"Warning: {self.name} cycle exceeded tick interval by: {cycle_perc - 100:.2f}%"
                    print(msg)
        return new_events

    def get_event_from_notification(self, notification):
        return self.event_store.mapper.event_from_topic_and_state(
            topic=notification['topic'],
            state=notification['state']
        )

    def get_notification_generator(self, upstream_name, advance_by):
        # Dict avoids re-entrant calls to run() starting their own generator,
        # so that notifications are only received once. Was needed in
        # single-threaded runner before it was changed to use iteration not
        # recursion. Hence, probably no longer needed - use reader directly.
        try:
            generator = self._notification_generators[upstream_name]
        except KeyError:
            # Todo: Rename as 'iterator'? We use an iterator, doesn't matter whether or not it is a generator.
            generator = self.read_reader(upstream_name, advance_by)
            self._notification_generators[upstream_name] = generator
        return generator

    def read_reader(self, upstream_name, advance_by=None):
        return self.readers[upstream_name].read(advance_by=advance_by)

    def del_notification_generator(self, upstream_name):
        try:
            del self._notification_generators[upstream_name]
        except KeyError:
            pass

    def take_snapshots(self, new_events):
        pass

    def set_reader_position_from_tracking_records(self, upstream_name):
        max_record_id = self.event_store.record_manager.get_max_tracking_record_id(upstream_name)
        reader = self.readers[upstream_name]
        reader.seek(max_record_id or 0)

    def call_policy(self, event):
        # Get the application policy.
        policy = self.policy_func or self.policy

        # Wrap the actual repository, so we can collect aggregates.
        repository = RepositoryWrapper(self.repository)

        # Actually call the policy.
        new_aggregates = policy(repository, event)

        # Collect all aggregates.
        repo_aggregates = list(repository.retrieved_aggregates.values())
        all_aggregates = repo_aggregates[:]
        if new_aggregates is not None:
            if not isinstance(new_aggregates, (list, tuple)):
                new_aggregates = [new_aggregates]
                if self.repository._use_cache:
                    for new_aggregate in new_aggregates:
                        self.repository._cache[new_aggregate.id] = new_aggregate
            all_aggregates += new_aggregates

        # Identify causal dependencies.
        causal_dependencies = []
        if self.use_causal_dependencies:
            highest = defaultdict(int)
            for entity_id, entity_version in repository.causal_dependencies:
                pipeline_id, notification_id = self.event_store.record_manager.get_pipeline_and_notification_id(
                    entity_id, entity_version
                )
                if pipeline_id is not None and pipeline_id != self.pipeline_id:
                    highest[pipeline_id] = max(notification_id, highest[pipeline_id])

            causal_dependencies = []
            for pipeline_id, notification_id in highest.items():
                causal_dependencies.append({
                    'pipeline_id': pipeline_id,
                    'notification_id': notification_id
                })
        # Todo: Optionally reference causal dependencies in current pipeline.
        # Todo: Support processing notification from a single pipeline in parallel, according to dependencies.
        return all_aggregates, causal_dependencies

    @staticmethod
    def policy(repository, event):
        """Empty method, can be overridden in subclasses to implement concrete policy."""

    def collect_pending_events(self, aggregates):
        pending_events = []
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
            #    aggregate sequence, but if timestamps are skewed and so do not correctly
            #    order the events, the events may be out of order in their notification log.
            #    It is expected in normal usage that these events are created in the same
            #    operating system thread, with timestamps from the same operating system clock,
            #    and so the timestamps will provide the correct order. However, if somehow
            #    different events are timestamped from different clocks, then problems may occur
            #    if those clocks give timestamps that skew the correct causal order.
            pending_events.sort(key=lambda x: x.timestamp)

        return pending_events

    def construct_tracking_kwargs(self, notification_id, upstream_application_name):
        return {
            'application_name': self.name,
            'upstream_application_name': upstream_application_name,
            'pipeline_id': self.pipeline_id,
            'notification_id': notification_id,
        }

    def record_process_event(self, process_event):
        # Construct event records.
        event_records = self.construct_event_records(process_event.new_events,
                                                     process_event.causal_dependencies)

        # Write event records with tracking record.
        record_manager = self.event_store.record_manager
        assert isinstance(record_manager, ACIDRecordManager)
        record_manager.write_records(records=event_records,
                                     tracking_kwargs=process_event.tracking_kwargs)

    def construct_event_records(self, pending_events, causal_dependencies=None):
        # Convert to event records.
        sequenced_items = self.event_store.item_from_event(pending_events)
        event_records = self.event_store.record_manager.to_records(sequenced_items)

        # Set notification log IDs, and causal dependencies.
        if len(event_records):
            # Todo: Maybe keep track of what this probably is, to avoid query. Like log reader, invalidate on error.
            if self.set_notification_ids:
                current_max = self.event_store.record_manager.get_max_record_id() or 0
                for domain_event, event_record in zip(pending_events, event_records):
                    if type(domain_event).__notifiable__:
                        current_max += 1
                        event_record.id = current_max
                    else:
                        event_record.id = 'event-not-notifiable'

            if self.use_causal_dependencies:
                assert hasattr(self.event_store.record_manager.record_class, 'causal_dependencies')
                causal_dependencies = json_dumps(causal_dependencies)
                # Only need first event to carry the dependencies.
                event_records[0].causal_dependencies = causal_dependencies

        return event_records

    def setup_table(self):
        super(ProcessApplication, self).setup_table()
        if self.datastore is not None:
            self.datastore.setup_table(
                self.event_store.record_manager.tracking_record_class
            )

    def drop_table(self):
        super(ProcessApplication, self).drop_table()
        if self.datastore is not None:
            self.datastore.drop_table(
                self.event_store.record_manager.tracking_record_class
            )


class RepositoryWrapper(object):
    def __init__(self, repository):
        self.retrieved_aggregates = {}
        assert isinstance(repository, EventSourcedRepository)
        self.repository = repository
        self.causal_dependencies = []

    def __getitem__(self, entity_id):
        try:
            return self.retrieved_aggregates[entity_id]
        except KeyError:
            entity = self.repository.__getitem__(entity_id)
            self.retrieved_aggregates[entity_id] = entity
            self.causal_dependencies.append((entity.id, entity.__version__))
            return entity

    def __contains__(self, entity_id):
        return self.repository.__contains__(entity_id)


class Prompt(object):
    def __init__(self, process_name, pipeline_id):
        self.process_name = process_name
        self.pipeline_id = pipeline_id

    def __eq__(self, other):
        return (
            other
            and isinstance(other, type(self))
            and self.process_name == other.process_name
            and self.pipeline_id == other.pipeline_id
        )

    def __repr__(self):
        return "{}({}={}, {}={})".format(
            type(self).__name__,
            'process_name', self.process_name,
            'pipeline_id', self.pipeline_id
        )


class ProcessApplicationWithSnapshotting(SnapshottingApplication, ProcessApplication):
    def take_snapshots(self, new_events):
        for event in new_events:
            if self.snapshotting_policy.condition(event):
                self.snapshotting_policy.take_snapshot(event)
