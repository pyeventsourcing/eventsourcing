from collections import OrderedDict, defaultdict

from eventsourcing.application.pipeline import Pipeable
from eventsourcing.application.simple import Application
from eventsourcing.application.snapshotting import ApplicationWithSnapshotting
from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.entity import DomainEntity
from eventsourcing.domain.model.events import publish, subscribe, unsubscribe
from eventsourcing.exceptions import CausalDependencyFailed, OperationalError, PromptFailed, RecordConflictError
from eventsourcing.infrastructure.base import RelationalRecordManager
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.interface.notificationlog import NotificationLogReader
from eventsourcing.utils.transcoding import json_dumps, json_loads


class ProcessApplication(Pipeable, Application):
    always_track_notifications = True

    def __init__(self, name=None, policy=None, setup_table=False, always_track_notifications=False, **kwargs):
        self.always_track_notifications = always_track_notifications or self.always_track_notifications
        self.policy_func = policy
        self.readers = OrderedDict()
        self.is_reader_position_ok = defaultdict(bool)
        super(ProcessApplication, self).__init__(name=name, setup_table=setup_table, **kwargs)
        # self._cached_entities = {}

        ## Prompts policy.
        #
        # 1. Publish prompts whenever domain events are published (important: after persisted).
        # 2. Run this process whenever upstream prompted followers to pull for new notification.
        subscribe(predicate=self.persistence_policy.is_event, handler=self.publish_prompt_from_event)
        subscribe(predicate=self.is_upstream_prompt, handler=self.run)
        # Todo: Maybe make a prompts policy object?

    def follow(self, upstream_application_name, notification_log):
        # Create a reader.
        reader = NotificationLogReader(notification_log)
        self.readers[upstream_application_name] = reader

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

    @retry((OperationalError, RecordConflictError), max_attempts=100, wait=0.01)
    def run(self, prompt=None, advance_by=None):

        if prompt is None:
            readers_items = self.readers.items()
        else:
            assert isinstance(prompt, Prompt)
            reader = self.readers[prompt.process_name]
            readers_items = [(prompt.process_name, reader)]

        notification_count = 0
        for upstream_application_name, reader in readers_items:

            if not self.is_reader_position_ok[upstream_application_name]:
                self.set_reader_position_from_tracking_records(reader, upstream_application_name)
                self.is_reader_position_ok[upstream_application_name] = True

            for notification in reader.read(advance_by=advance_by):
                # Todo: Put this on a queue and then get the next one.
                notification_count += 1

                # Todo: Get this from a queue and do it in a different thread?
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
                        upstream_application_name=upstream_application_name,
                        pipeline_id=pipeline_id,
                        notification_id=notification_id
                    )
                    if not has_tracking_record:
                        # Invalidate reader position.
                        self.is_reader_position_ok[upstream_application_name] = False

                        # Raise exception.
                        raise CausalDependencyFailed({
                            'application_name': self.name,
                            'upstream_application_name': upstream_application_name,
                            'pipeline_id': pipeline_id,
                            'notification_id': notification_id
                        })

                # Call policy with the event.
                all_aggregates, causal_dependencies = self.call_policy(event)

                # Record new events.
                try:
                    new_events = self.record_new_events(
                        all_aggregates, notification, upstream_application_name, causal_dependencies
                    )
                except Exception as e:
                    self.is_reader_position_ok[upstream_application_name] = False
                    # self._cached_entities = {}
                    raise e
                else:
                    # Publish a prompt if there are new notifications.
                    # Todo: Optionally send events as prompts, saves pulling event if it arrives in order.
                    if len(new_events):
                        self.publish_prompt()

        return notification_count

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

    def record_new_events(self, aggregates, notification=None, upstream_application_name=None,
                          causal_dependencies=None):
        # Construct tracking record.
        tracking_kwargs = self.construct_tracking_kwargs(notification, upstream_application_name)

        # Collect pending events.
        new_events, num_changed_aggregates = self.collect_pending_events(aggregates)

        # Writing tracking record when there are new events.
        if len(new_events) or self.always_track_notifications:

            # Sort pending events across all aggregates.
            if num_changed_aggregates > 1:
                self.sort_pending_events(new_events)

            # Construct event records.
            event_records = self.construct_event_records(new_events, causal_dependencies)

            # Write event records with tracking record.
            record_manager = self.event_store.record_manager
            assert isinstance(record_manager, RelationalRecordManager)
            record_manager.write_records(records=event_records, tracking_kwargs=tracking_kwargs)
        # else:
            # Todo: Maybe write one tracking record at the end of a run, if necessary, or
            # only during a period of time when nothing happens?

        return new_events

    def sort_pending_events(self, pending_events):
        # Sort the events by timestamp.
        #  - this approximation is a supposed to correlate with the correct
        #    causal ordering of all new events across all aggregates. It
        #    should work if all events are timestamped, all their timestamps
        #    are from the same clock, and none have the same value. If this
        #    doesn't work properly, it is possible when several aggregates
        #    publish that depend on each other that concatenating pending events
        #    taken from each in turn will be incorrect and could potentially
        #    cause processing errors in a downstream process application that
        #    somehow depends on the correct ordering of events.
        try:
            pending_events.sort(key=lambda x: x.timestamp)
        except AttributeError:
            pass

    def is_upstream_prompt(self, prompt):
        return isinstance(prompt, Prompt) and prompt.process_name in self.readers.keys()

    def publish_prompt_from_event(self, _):
        self.publish_prompt()

    def publish_prompt(self):
        prompt = Prompt(self.name, self.pipeline_id)
        try:
            publish(prompt)
        except PromptFailed:
            raise
        except Exception as e:
            raise PromptFailed("{}: {}".format(type(e), str(e)))

    def construct_event_records(self, pending_events, causal_dependencies=None):
        # Convert to event records.
        sequenced_items = self.event_store.to_sequenced_item(pending_events)
        event_records = self.event_store.record_manager.to_records(sequenced_items)

        # Set notification log IDs, and causal dependencies.
        if len(event_records):
            current_max = self.event_store.record_manager.get_max_record_id() or 0
            for domain_event, event_record in zip(pending_events, event_records):
                if type(domain_event).__notifiable__:
                    current_max += 1
                    event_record.id = current_max
                else:
                    event_record.id = ''

            # Only need first event to carry the dependencies.
            if hasattr(self.event_store.record_manager.record_class, 'causal_dependencies'):
                causal_dependencies = json_dumps(causal_dependencies)
                event_records[0].causal_dependencies = causal_dependencies

        return event_records

    def collect_pending_events(self, aggregates):
        if isinstance(aggregates, DomainEntity):
            aggregates = [aggregates]
        assert isinstance(aggregates, (list, tuple))
        pending_events = []
        num_changed_aggregates = 0
        for aggregate in aggregates:
            batch = aggregate.__batch_pending_events__()
            if len(batch):
                num_changed_aggregates += 1
            pending_events += batch
        return pending_events, num_changed_aggregates

    def construct_tracking_kwargs(self, notification, upstream_application_name):
        if notification is None:
            return {}
        tracking_kwargs = {
            'application_name': self.name,
            'upstream_application_name': upstream_application_name,
            'pipeline_id': self.pipeline_id,
            'notification_id': notification['id'],
        }
        return tracking_kwargs

    def close(self):
        unsubscribe(predicate=self.is_upstream_prompt, handler=self.run)
        unsubscribe(predicate=self.persistence_policy.is_event, handler=self.publish_prompt_from_event)
        super(ProcessApplication, self).close()

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


class ProcessApplicationWithSnapshotting(ApplicationWithSnapshotting, ProcessApplication):
    def record_new_events(self, *args, **kwargs):
        new_events = super(ProcessApplicationWithSnapshotting, self).record_new_events(*args, **kwargs)
        for event in new_events:
            if self.snapshotting_policy.condition(event):
                self.snapshotting_policy.take_snapshot(event)
        return new_events
