from collections import OrderedDict

from eventsourcing.application.simple import SimpleApplication
from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.domain.model.events import EventWithOriginatorID, publish, subscribe, unsubscribe
from eventsourcing.exceptions import ConcurrencyError, SequencedItemConflict, OperationalError
from eventsourcing.infrastructure.base import RelationalRecordManager
from eventsourcing.infrastructure.sqlalchemy.manager import TrackingRecordManager
from eventsourcing.interface.notificationlog import NotificationLogReader
from eventsourcing.utils.uuids import uuid_from_application_name


class Prompt(object):
    def __init__(self, sender_process_name, end_position=None):
        self.sender_process_name = sender_process_name
        self.end_position = end_position


class Process(SimpleApplication):
    tracking_record_manager_class = TrackingRecordManager

    def __init__(self, name=None, policy=None, setup_table=True, session=None, persist_event_type=None, **kwargs):
        persist_event_type = persist_event_type or AggregateRoot.Event
        super(Process, self).__init__(name=name, setup_table=setup_table, session=session,
                                      persist_event_type=persist_event_type, **kwargs)
        self.policy_func = policy
        self.readers = OrderedDict()

        # Setup tracking records.
        self.tracking_record_manager = self.tracking_record_manager_class(self.datastore.session)
        if setup_table and not session:
            self.datastore.setup_table(
                self.tracking_record_manager.record_class
            )

        # Subscribe to publish prompts after domain events are persisted.
        subscribe(predicate=self.persistence_policy.is_event, handler=self.publish_prompt)

        # Subscribe to run process when prompted.
        subscribe(predicate=self.is_upstream_prompt, handler=self.run)

    def is_upstream_prompt(self, event):
        return isinstance(event, Prompt) and event.sender_process_name in self.readers.keys()

    def publish_prompt(self, event=None):
        prompt = Prompt(
            sender_process_name=self.name,
            # end_position=self.notification_log.get_end_position()
        )
        publish(prompt)

    def follow(self, upstream_application_name, notification_log):
        # Create a reader.
        reader = NotificationLogReader(notification_log)
        self.reset_position(reader, upstream_application_name)
        self.readers[upstream_application_name] = reader

    def reset_position(self, reader, upstream_application_name):
        max_record_id = self.tracking_record_manager.get_max_record_id(
            application_name=self.name,
            upstream_application_name=upstream_application_name,
        )
        current_position = max_record_id or 0
        reader.seek(current_position)

    def run(self, prompt=None):
        notification_count = 0
        for upstream_application_name, reader in self.readers.items():

            if prompt and prompt.sender_process_name != upstream_application_name:
                continue

            # Todo: Change this to use a generator (rather than a list).
            continue_reading = True
            while continue_reading:
                try:
                    for notification in reader.read_items(advance_by=10):
                        notification_count += 1
                        # Domain event from notification.
                        event = self.event_store.sequenced_item_mapper.from_topic_and_data(
                            topic=notification['event_type'],
                            data=notification['state']
                        )

                        # Execute the policy with the event.
                        unsaved_aggregates, causal_dependencies = self.policy(event)

                        # Write records.
                        self.write_records(unsaved_aggregates, notification, self.name, upstream_application_name)
                        # Todo: Use causal_dependencies to construct notification records (depends on notification
                        # records).

                    else:
                        continue_reading = False
                except (OperationalError, ConcurrencyError):
                    self.reset_position(reader, upstream_application_name)

        # Publish a prompt if there are new notifications.
        if notification_count:
            self.publish_prompt()

        return notification_count

    def policy(self, event):
        return self.policy_func(self, event)

    def get_originator(self, event):
        assert isinstance(event, EventWithOriginatorID), type(event)
        return self.repository[event.originator_id]

    def write_records(self, aggregates, notification, application_name, upstream_application_name):
        # Construct tracking record.
        tracking_record = self.construct_tracking_record(notification, application_name, upstream_application_name)

        # Construct event records.
        event_records = self.construct_event_records(aggregates)

        # Write event records with tracking record.
        record_manager = self.event_store.record_manager
        assert isinstance(record_manager, RelationalRecordManager)
        try:
            record_manager.write_records(records=event_records, tracking_record=tracking_record)
        except SequencedItemConflict as e:
            raise ConcurrencyError(e)

    def construct_event_records(self, aggregates):
        if aggregates is None:
            aggregates = []
        elif not isinstance(aggregates, (list, tuple)):
            aggregates = [aggregates]
        event_records = []

        record_manager = self.event_store.record_manager

        for aggregate in aggregates:
            pending_events = aggregate.__batch_pending_events__()
            sequenced_items = self.event_store.to_sequenced_item(pending_events)
            assert isinstance(record_manager, RelationalRecordManager)
            event_records += record_manager.to_records(sequenced_items)

        current_max = record_manager.get_max_record_id() or 0
        for event_record in event_records:
            current_max += 1
            event_record.id = current_max

        return event_records

    def construct_tracking_record(self, notification, application_name, upstream_application_name):
        application_id = uuid_from_application_name(application_name)
        upstream_application_id = uuid_from_application_name(upstream_application_name)
        partition_id = application_id
        kwargs = {
            'notification_id': notification['id'],
            'application_id': application_id,
            'upstream_application_id': upstream_application_id,
            'partition_id': partition_id,
            'originator_id': notification['originator_id'],
            'originator_version': notification['originator_version']
        }
        return self.tracking_record_manager.record_class(**kwargs)

    def close(self):
        unsubscribe(predicate=self.is_upstream_prompt, handler=self.run)
        unsubscribe(predicate=self.persistence_policy.is_event, handler=self.publish_prompt)
        super(Process, self).close()
