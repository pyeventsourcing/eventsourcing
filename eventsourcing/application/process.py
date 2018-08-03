from collections import OrderedDict, defaultdict

from eventsourcing.application.pipeline import Pipeable
from eventsourcing.application.simple import Application
from eventsourcing.application.snapshotting import SnapshottingApplication
from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.events import publish, subscribe, unsubscribe
from eventsourcing.exceptions import CausalDependencyFailed, OperationalError, PromptFailed, RecordConflictError
from eventsourcing.infrastructure.base import ACIDRecordManager
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.interface.notificationlog import NotificationLogReader
from eventsourcing.utils.transcoding import json_dumps, json_loads


class ProcessEvent(object):
    def __init__(self, new_events, tracking_kwargs=None, causal_dependencies=None):
        self.new_events = new_events
        self.tracking_kwargs = tracking_kwargs
        self.causal_dependencies = causal_dependencies


class ProcessApplication(Pipeable, Application):

    def __init__(self, name=None, policy=None, setup_table=False, **kwargs):
        self.policy_func = policy
        self.readers = OrderedDict()
        self.is_reader_position_ok = defaultdict(bool)
        super(ProcessApplication, self).__init__(name=name, setup_table=setup_table, **kwargs)

        subscribe(self.run, self.is_upstream_prompt)
        subscribe(self.publish_prompt, self.persistence_policy.is_event)

    def close(self):
        unsubscribe(self.run, self.is_upstream_prompt)
        unsubscribe(self.publish_prompt, self.persistence_policy.is_event)
        super(ProcessApplication, self).close()

    def is_upstream_prompt(self, prompt):
        return isinstance(prompt, Prompt) and prompt.process_name in self.readers.keys()

    def publish_prompt(self, event=None):
        """
        Publishes prompt for a given event.

        Used to prompt downstream process application when an event
        is published by this application's model, which can happen
        when application command methods, rather than the process policy,
        are called.
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
        reader = NotificationLogReader(notification_log)
        self.readers[upstream_application_name] = reader

    @retry((OperationalError, RecordConflictError), max_attempts=100, wait=0.01)
    def run(self, prompt=None, advance_by=None):

        if prompt is None:
            readers_items = self.readers.items()
        else:
            assert isinstance(prompt, Prompt)
            reader = self.readers[prompt.process_name]
            readers_items = [(prompt.process_name, reader)]

        notification_count = 0
        for upstream_name, reader in readers_items:

            if not self.is_reader_position_ok[upstream_name]:
                self.set_reader_position_from_tracking_records(reader, upstream_name)
                self.is_reader_position_ok[upstream_name] = True

            # Todo: Change to use queue, so next notification is more likely already loaded?
            for notification in reader.read(advance_by=advance_by):
                notification_count += 1

                # Get domain event from notification.
                event = self.event_store.sequenced_item_mapper.from_topic_and_data(
                    topic=notification['event_type'],
                    data=notification['state']
                )

                # Decode causal dependencies of the domain event.
                causal_dependencies = notification.get('causal_dependencies') or '[]'
                causal_dependencies = json_loads(causal_dependencies) or []

                # Check causal dependencies are satisfied.
                for causal_dependency in causal_dependencies:
                    pipeline_id = causal_dependency['pipeline_id']
                    notification_id = causal_dependency['notification_id']

                    has_tracking_record = self.event_store.record_manager.has_tracking_record(
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

                # Call policy with the upstream event.
                all_aggregates, causal_dependencies = self.call_policy(event)

                # Collect pending events.
                new_events = self.collect_pending_events(all_aggregates)

                # Record process event.
                try:
                    tracking_kwargs = self.construct_tracking_kwargs(
                        notification, upstream_name
                    )
                    process_event = ProcessEvent(
                        new_events, tracking_kwargs, causal_dependencies
                    )
                    self.record_process_event(process_event)

                    # Todo: Maybe write one tracking record at the end of a run, if
                    # necessary, or only during a period of time when nothing happens?
                except Exception as e:
                    self.is_reader_position_ok[upstream_name] = False
                    # self._cached_entities = {}
                    raise e
                else:
                    # Publish a prompt if there are new notifications.
                    # Todo: Optionally send events as prompts, saves pulling event if it arrives in order.
                    self.take_snapshots(new_events)

                    if new_events:
                        self.publish_prompt()

        return notification_count

    def take_snapshots(self, new_events):
        pass

    def set_reader_position_from_tracking_records(self, reader, upstream_application_name):
        max_record_id = self.event_store.record_manager.get_max_tracking_record_id(upstream_application_name)
        reader.seek(max_record_id or 0)

    def call_policy(self, event):
        policy = self.policy_func or self.policy
        repository = RepositoryWrapper(self.repository)
        new_aggregates = policy(repository, event)
        repo_aggregates = list(repository.retrieved_aggregates.values())
        all_aggregates = repo_aggregates[:]
        if new_aggregates is not None:
            if not isinstance(new_aggregates, (list, tuple)):
                new_aggregates = [new_aggregates]
            all_aggregates += new_aggregates

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

    def construct_tracking_kwargs(self, notification, upstream_application_name):
        if notification:
            return {
                'application_name': self.name,
                'upstream_application_name': upstream_application_name,
                'pipeline_id': self.pipeline_id,
                'notification_id': notification['id'],
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
        sequenced_items = self.event_store.to_sequenced_item(pending_events)
        event_records = self.event_store.record_manager.to_records(sequenced_items)

        # Set notification log IDs, and causal dependencies.
        if len(event_records):
            # Todo: Maybe keep track of what this probably is, to avoid query. Like log reader, invalidate on error.
            current_max = self.event_store.record_manager.get_max_record_id() or 0
            for domain_event, event_record in zip(pending_events, event_records):
                if type(domain_event).__notifiable__:
                    current_max += 1
                    event_record.id = current_max
                else:
                    event_record.id = 'event-not-notifiable'

            # Only need first event to carry the dependencies.
            if hasattr(self.event_store.record_manager.record_class, 'causal_dependencies'):
                causal_dependencies = json_dumps(causal_dependencies)
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

    @classmethod
    def reset_connection_after_forking(cls):
        """
        Resets database connection after forking.
        """


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
