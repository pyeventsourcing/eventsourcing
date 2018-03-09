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


class Process(SimpleApplication):
    tracking_record_manager_class = TrackingRecordManager

    def __init__(self, name=None, policy=None, setup_tables=False, setup_table=False, session=None,
                 persist_event_type=None, **kwargs):
        setup_table = setup_tables = setup_table or setup_tables
        super(Process, self).__init__(name=name, setup_table=setup_table, session=session,
                                      persist_event_type=persist_event_type, **kwargs)
        self._cached_entities = {}
        self.policy_func = policy
        self.readers = OrderedDict()
        self.is_reader_position_ok = defaultdict(bool)

        # Setup tracking records.
        self.tracking_record_manager = self.tracking_record_manager_class(self.datastore.session)
        if setup_tables and not session:
            self.datastore.setup_table(
                self.tracking_record_manager.record_class
            )

        ## Prompts policy.
        #
        # 1. Publish prompts whenever domain events are published (important: after persisted).
        # 2. Run this process whenever upstream prompted followers to pull for new notification.
        subscribe(predicate=self.persistence_policy.is_event, handler=self.publish_prompt)
        subscribe(predicate=self.is_upstream_prompt, handler=self.run)
        # Todo: Maybe make a prompts policy object?

    def follow(self, upstream_application_name, notification_log):
        # Create a reader.
        reader = NotificationLogReader(notification_log)
        self.readers[upstream_application_name] = reader

    @retry((OperationalError, RecordConflictError), max_attempts=100, wait=0.01)
    def run(self, prompt=None):

        if prompt is None:
            readers_items = self.readers.items()
        else:
            assert isinstance(prompt, Prompt)
            # Todo: This in a better way.
            upstream_application_name = prompt.channel_name.split('-')[0]
            reader = self.readers[upstream_application_name]
            readers_items = [(upstream_application_name, reader)]

        notification_count = 0
        for upstream_application_name, reader in readers_items:

            if not self.is_reader_position_ok[upstream_application_name]:
                self.set_reader_position_from_tracking_records(reader, upstream_application_name)
                self.is_reader_position_ok[upstream_application_name] = True

            # for notification in reader.read(advance_by=self.notification_log_section_size):
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
                # Todo: Also include the received event in the causal dependencies.

                # Write records.
                try:
                    event_records = self.write_records(
                        unsaved_aggregates, notification, upstream_application_name
                    )
                except Exception as e:
                    self.is_reader_position_ok[upstream_application_name] = False
                    self._cached_entities = {}
                    raise e
                else:
                    # Publish a prompt if there are new notifications.
                    # Todo: Optionally send events as prompts, will save reading database
                    # if it arrives in correct order, but risks overloading the recipient.
                    if event_records:
                        self.publish_prompt()

        return notification_count

    def set_reader_position_from_tracking_records(self, reader, upstream_application_name):
        max_record_id = self.tracking_record_manager.get_max_record_id(
            application_name=self.name,
            upstream_application_name=upstream_application_name,
            partition_id=self.partition_id,
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

    def write_records(self, aggregates, notification, upstream_application_name):
        # Construct tracking record.
        tracking_record = self.construct_tracking_record(notification, upstream_application_name)

        # Construct event records.
        event_records = self.construct_event_records(aggregates)

        # Todo: Optimise by skipping writing lots of solo tracking records.
        # Todo: - maybe just write one at the end of a run, if necessary, or only once during a period of time when
        # nothing happens

        # # Write event records with tracking record.
        # if event_records:
        #     write_records = True
        # elif notification['id'] % 10 == 0:
        #     write_records = True
        # else:
        #     # write_records = False
        write_records = True

        if write_records:
            record_manager = self.event_store.record_manager
            assert isinstance(record_manager, RelationalRecordManager)
            record_manager.write_records(records=event_records, tracking_record=tracking_record)

        return event_records

    def is_upstream_prompt(self, event):
        return isinstance(event, Prompt) and event.channel_name.split('-')[0] in self.readers.keys()

    def publish_prompt(self, _=None):
        prompt = Prompt(make_channel_name(self.name, self.partition_id))
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

    def construct_tracking_record(self, notification, upstream_application_name):
        upstream_application_id = uuid_from_application_name(upstream_application_name)
        kwargs = {
            'application_id': self.application_id,
            'upstream_application_id': upstream_application_id,
            'partition_id': self.partition_id,
            'notification_id': notification['id'],
            'originator_id': notification['originator_id'],
            'originator_version': notification['originator_version']
        }
        return self.tracking_record_manager.record_class(**kwargs)

    def close(self):
        unsubscribe(predicate=self.is_upstream_prompt, handler=self.run)
        unsubscribe(predicate=self.persistence_policy.is_event, handler=self.publish_prompt)
        super(Process, self).close()


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


class Prompt(object):
    def __init__(self, channel_name, end_position=None):
        self.channel_name = channel_name
        self.end_position = end_position


class System(object):
    def __init__(self, *definition):
        """
        Initialises a "process network" system object.

        :param definition: Sequences of process classes.

        Each sequence of process classes shows directly which process
        follows which other process in the system.

        For example, the sequence (A, B, C) shows that B follows A,
        and C follows B.

        The sequence (A, A) shows that A follows A.

        The sequence (A, B, A) shows that B follows A, and A follows B.

        The sequences ((A, B, A), (A, C, A)) is equivalent to (A, B, A, C, A).
        """
        self.processes_by_name = None
        self.definition = definition
        assert isinstance(self.definition, (list, tuple))
        self.process_classes = set([c for l in self.definition for c in l])

        # Determine which process follows which.
        self.followings = OrderedDict()
        for sequence in self.definition:
            previous = None
            for process_class in sequence:
                assert issubclass(process_class, Process), process_class
                if previous is not None:
                    # Follower follows the followed.
                    follower = process_class
                    followed = previous
                    try:
                        follows = self.followings[follower]
                    except KeyError:
                        follows = []
                        self.followings[follower] = follows

                    if followed not in follows:
                        follows.append(followed)

                previous = process_class

    # Todo: Move this to 'Singlethread' class or something (like the 'Multiprocess' class)?
    def setup(self):
        assert self.processes_by_name is None, "Already running"
        self.processes_by_name = {}
        session = None

        # Construct the processes.
        for process_class in self.process_classes:
            process = process_class(session=session, setup_tables=bool(session is None))
            self.processes_by_name[process.name] = process
            if session is None:
                session = process.session

        # Configure which process follows which.
        for follower_class, follows in self.followings.items():
            follower = self.processes_by_name[follower_class.__name__.lower()]
            for followed_class in follows:
                followed = self.processes_by_name[followed_class.__name__.lower()]
                follower.follow(followed.name, followed.notification_log)

    def __getattr__(self, process_name):
        assert self.processes_by_name is not None, "Not running"
        return self.processes_by_name[process_name]

    def close(self):
        assert self.processes_by_name is not None, "Not running"
        for process in self.processes_by_name.values():
            process.close()
        self.processes_by_name = None

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def make_channel_name(name, partition_id):
    return "{}-{}".format(name, partition_id)
