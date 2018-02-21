from collections import OrderedDict

from eventsourcing.application.simple import SimpleApplication
from eventsourcing.domain.model.events import EventWithOriginatorID
from eventsourcing.exceptions import SequencedItemConflict, ConcurrencyError
from eventsourcing.infrastructure.base import RelationalRecordManager
from eventsourcing.interface.notificationlog import NotificationLogReader
from eventsourcing.infrastructure.sqlalchemy.manager import TrackingRecordManager
from eventsourcing.utils.uuids import uuid_from_application_name


class Process(SimpleApplication):
    def __init__(self, policy, **kwargs):
        super(Process, self).__init__(**kwargs)
        self.policy = policy
        self.readers = OrderedDict()
        self.tracking_record_manager = TrackingRecordManager(self.datastore.session)
        self.datastore.setup_table(
            self.tracking_record_manager.record_class
        )

    def follow(self, notification_log, application_name):
        reader = NotificationLogReader(notification_log)
        current_position = self.tracking_record_manager.get_max_record_id(application_name) or 0
        reader.seek(current_position)
        self.readers[application_name] = reader

    def run(self):
        notification_count = 0
        for upstream_application_name, reader in self.readers.items():
            for notification in reader.read():
                notification_count += 1
                # Domain event from notification.
                event = self.event_store.sequenced_item_mapper.from_topic_and_data(
                    topic=notification['event_type'],
                    data=notification['state']
                )

                # Execute the policy with the event.
                unsaved_aggregates, causal_dependencies = self.policy(self, event)

                # Todo: Use causal_dependencies to construct notification records (depends on notification records).
                # Write records.
                self.write_records(unsaved_aggregates, notification, upstream_application_name)

        return notification_count

    def get_originator(self, event):
        assert isinstance(event, EventWithOriginatorID)
        return self.repository[event.originator_id]

    def write_records(self, aggregates, notification, upstream_application_name):
        # Construct tracking record.
        tracking_record = self.construct_tracking_record(notification, upstream_application_name)

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
        for aggregate in aggregates:
            pending_events = aggregate.__batch_pending_events__()
            sequenced_items = self.event_store.to_sequenced_item(pending_events)
            record_manager = self.event_store.record_manager
            assert isinstance(record_manager, RelationalRecordManager)
            event_records += record_manager.to_records(sequenced_items)
        return event_records

    def construct_tracking_record(self, notification, upstream_application_name):
        application_id = uuid_from_application_name(upstream_application_name)
        partition_id = application_id
        kwargs = {
            'notification_id': notification['id'],
            'application_id': application_id,
            'partition_id': partition_id,
            'originator_id': notification['originator_id'],
            'originator_version': notification['originator_version']
        }
        return self.tracking_record_manager.record_class(**kwargs)
