from collections import OrderedDict, defaultdict
from uuid import UUID

from eventsourcing.application.simple import SimpleApplication
from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.events import EventWithOriginatorID, publish, subscribe, unsubscribe
from eventsourcing.exceptions import OperationalError, PromptFailed, RecordConflictError
from eventsourcing.infrastructure.base import RelationalRecordManager
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.sqlalchemy.manager import TrackingRecordManager
from eventsourcing.interface.notificationlog import NotificationLogReader
from eventsourcing.utils.uuids import uuid_from_application_name


class Prompt(object):
    def __init__(self, sender_process_name, end_position=None):
        self.sender_process_name = sender_process_name
        self.end_position = end_position


class RepositoryWrapper(object):
    def __init__(self, repository):
        self.retrieved_aggregates = {}
        assert isinstance(repository, EventSourcedRepository)
        self.repository = repository

    def __getitem__(self, entity_id):
        try:
            return self.retrieved_aggregates[entity_id]
        except KeyError:
            entity = self.repository.__getitem__(entity_id)
            self.retrieved_aggregates[entity_id] = entity
            return entity

    def __contains__(self, entity_id):
        return self.repository.__contains__(entity_id)


class Process(SimpleApplication):
    tracking_record_manager_class = TrackingRecordManager

    def __init__(self, name=None, policy=None, setup_table=True, session=None, persist_event_type=None, **kwargs):
        super(Process, self).__init__(name=name, setup_table=setup_table, session=session,
                                      persist_event_type=persist_event_type, **kwargs)
        self._cached_entities = {}
        self.policy_func = policy
        self.readers = OrderedDict()
        self.is_reader_position_ok = defaultdict(bool)

        # Setup tracking records.
        self.tracking_record_manager = self.tracking_record_manager_class(self.datastore.session)
        if setup_table and not session:
            self.datastore.setup_table(
                self.tracking_record_manager.record_class
            )

        # Todo: Maybe make a prompts policy object?
        #
        ## Prompts policy.
        #
        # 1. Publish prompts whenever domain events are published (important: after persisted).
        # 2. Run this process whenever upstream prompted followers to pull for new notification.
        subscribe(predicate=self.persistence_policy.is_event, handler=self.publish_prompt)
        subscribe(predicate=self.is_upstream_prompt, handler=self.run)

    def follow(self, upstream_application_name, notification_log):
        # Create a reader.
        reader = NotificationLogReader(notification_log)
        self.readers[upstream_application_name] = reader

    @retry((OperationalError, RecordConflictError), max_attempts=100, wait=0.01)
    def run(self, prompt=None):

        if prompt is None:
            readers_items = self.readers.items()
        else:
            upstream_application_name = prompt.sender_process_name
            reader = self.readers[prompt.sender_process_name]
            readers_items = [(upstream_application_name, reader)]

        notification_count = 0
        for upstream_application_name, reader in readers_items:

            if not self.is_reader_position_ok[upstream_application_name]:
                self.set_reader_position_from_tracking_records(reader, upstream_application_name)
                self.is_reader_position_ok[upstream_application_name] = True

            for notification in reader.read():
                # Todo: Put this on a queue and then get the next one.
                notification_count += 1

                # Todo: Get this from a queue and do it in a different thread?
                # Domain event from notification.
                event = self.event_store.sequenced_item_mapper.from_topic_and_data(
                    topic=notification['event_type'],
                    data=notification['state']
                )

                # Call policy with the event.
                unsaved_aggregates, causal_dependencies = self.call_policy(event)

                # Write records.
                try:
                    new_notification_ids = self.write_records(
                        unsaved_aggregates, notification, self.name, upstream_application_name
                    )
                except:
                    self.is_reader_position_ok[upstream_application_name] = False
                    self._cached_entities = {}
                    raise
                else:
                    # Publish a prompt if there are new notifications.
                    if new_notification_ids:
                        # self.publish_prompt(max(new_notification_ids))
                        self.publish_prompt('')
                    # try:
                    #     max_notification_id = max(new_notification_ids)
                    # except ValueError:
                    #     pass
                    # else:
                    #     self.publish_prompt(max_notification_id)

                # Todo: Use causal_dependencies to construct notification records (depends on notification
                # records).

        return notification_count

    def set_reader_position_from_tracking_records(self, reader, upstream_application_name):
        max_record_id = self.tracking_record_manager.get_max_record_id(
            application_name=self.name,
            upstream_application_name=upstream_application_name,
        )
        reader.seek(max_record_id or 0)

    def call_policy(self, event):
        repository = RepositoryWrapper(self.repository)
        causal_dependencies = []
        new_aggregates = self.policy(repository, event)
        unsaved_aggregates = list(repository.retrieved_aggregates.values())
        if new_aggregates is not None:
            if not isinstance(new_aggregates, (list, tuple)):
                new_aggregates = [new_aggregates]
            unsaved_aggregates += new_aggregates
        return unsaved_aggregates, causal_dependencies

    def policy(self, repository, event):
        return self.policy_func(self, repository, event)

    def write_records(self, aggregates, notification, application_name, upstream_application_name):
        # Construct tracking record.
        tracking_record = self.construct_tracking_record(notification, application_name, upstream_application_name)

        # Construct event records.
        event_records = self.construct_event_records(aggregates)

        # Write event records with tracking record.
        record_manager = self.event_store.record_manager
        assert isinstance(record_manager, RelationalRecordManager)
        record_manager.write_records(records=event_records, tracking_record=tracking_record)

        new_notification_ids = [e.id for e in event_records]
        return new_notification_ids

    def is_upstream_prompt(self, event):
        return isinstance(event, Prompt) and event.sender_process_name in self.readers.keys()

    def publish_prompt(self, max_notification_id=''):
        # if not isinstance(max_notification_id, six.integer_types):
        #     max_notification_id = None
        prompt = Prompt(
            sender_process_name=self.name,
            end_position=max_notification_id
        )
        try:
            publish(prompt)
        except Exception as e:
            raise PromptFailed("{}: {}".format(type(e), str(e)))

    def get_originator(self, event_or_id, use_cache=True):
        if isinstance(event_or_id, EventWithOriginatorID):
            originator_id = event_or_id.originator_id
        else:
            originator_id = event_or_id
        assert isinstance(originator_id, UUID), type(originator_id)
        if use_cache:
            try:
                originator = self._cached_entities[originator_id]
            except KeyError:
                originator = self.repository[originator_id]
                self._cached_entities[originator_id] = originator
        else:
            originator = self.repository[originator_id]
        return originator

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


class System(object):
    def __init__(self, *definition):
        self.definition = definition
        assert isinstance(self.definition, (list, tuple))
        for pair in self.definition:
            assert len(pair) == 2, len(pair)
            for process_class in pair:
                assert issubclass(process_class, Process), process_class
        self.processes_by_class = None
        self.classes_by_process_name = None

    def __getattr__(self, item):
        process_class = self.classes_by_process_name[item]
        return self.processes_by_class[process_class]

    def setup(self):
        assert self.processes_by_class is None, "Already running"
        self.process_classes = set([pc for pair in self.definition for pc in pair])
        self.processes_by_class = {}
        self.classes_by_process_name = {}
        session = None
        for process_class in self.process_classes:
            process = process_class(session=session)
            self.processes_by_class[process_class] = process
            self.classes_by_process_name[process.name] = process_class
            if session is None:
                session = process.session

        for follower_class, followed_class in self.definition:
            follower = self.processes_by_class[follower_class]
            followed = self.processes_by_class[followed_class]
            follower.follow(followed.name, followed.notification_log)

    def close(self):
        assert self.processes_by_class is not None, "Not running"
        for process in self.processes_by_class.values():
            process.close()
        self.processes_by_class = None
        self.classes_by_process_name = None
