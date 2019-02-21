from abc import ABC

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.entity import VersionedEntity
from eventsourcing.domain.model.events import Logged
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.example.domainmodel import create_new_example
from eventsourcing.example.infrastructure import ExampleRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy
from eventsourcing.utils.transcoding import ObjectJSONDecoder, ObjectJSONEncoder


# Please note, the code is this module is basically old-fashioned, and will
# be removed when the tests that depend on it are rewritten to use the new
# application classes in package eventsourcing.application. These were the
# original base classes for event sourced applications, but were set aside
# in favour of the new, less complicated application base classes


class ApplicationWithEventStores(ABC):
    """
    Event sourced application object class.

    Can construct event stores using given database records.
    Supports three different event stores: for log events,
    for entity events, and for snapshot events.
    """

    def __init__(self, entity_record_manager=None,
                 log_record_manager=None,
                 snapshot_record_manager=None,
                 cipher=None,
                 sequenced_item_mapper_class=SequencedItemMapper):

        self.entity_event_store = None
        if entity_record_manager:
            self.entity_event_store = self.construct_event_store(
                event_sequence_id_attr='originator_id',
                event_position_attr='originator_version',
                record_manager=entity_record_manager,
                cipher=cipher,
                sequenced_item_mapper_class=sequenced_item_mapper_class,
            )

        self.log_event_store = None
        if log_record_manager:
            self.log_event_store = self.construct_event_store(
                event_sequence_id_attr='originator_id',
                event_position_attr='timestamp',
                record_manager=log_record_manager,
                cipher=cipher,
                sequenced_item_mapper_class=sequenced_item_mapper_class,
            )

        self.snapshot_event_store = None
        if snapshot_record_manager:
            self.snapshot_event_store = self.construct_event_store(
                event_sequence_id_attr='originator_id',
                event_position_attr='originator_version',
                record_manager=snapshot_record_manager,
                cipher=cipher,
                sequenced_item_mapper_class=sequenced_item_mapper_class,
            )

    def construct_event_store(self, sequenced_item_mapper_class, event_sequence_id_attr, event_position_attr,
                              record_manager, cipher=None):
        sequenced_item_mapper = self.construct_sequenced_item_mapper(
            sequenced_item_mapper_class=sequenced_item_mapper_class,
            sequenced_item_class=record_manager.sequenced_item_class,
            event_sequence_id_attr=event_sequence_id_attr,
            event_position_attr=event_position_attr,
            cipher=cipher,
        )
        event_store = EventStore(
            record_manager=record_manager,
            sequenced_item_mapper=sequenced_item_mapper,
        )
        return event_store

    def construct_sequenced_item_mapper(self,
                                        sequenced_item_mapper_class,
                                        sequenced_item_class,
                                        event_sequence_id_attr,
                                        event_position_attr,
                                        cipher=None,
                                        json_encoder_class=ObjectJSONEncoder,
                                        json_decoder_class=ObjectJSONDecoder):
        return sequenced_item_mapper_class(
            sequenced_item_class=sequenced_item_class,
            sequence_id_attr_name=event_sequence_id_attr,
            position_attr_name=event_position_attr,
            json_encoder_class=json_encoder_class,
            json_decoder_class=json_decoder_class,
            cipher=cipher,
        )

    def close(self):
        self.entity_event_store = None
        self.log_event_store = None
        self.snapshot_event_store = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class ApplicationWithPersistencePolicies(ApplicationWithEventStores):
    def __init__(self, **kwargs):
        super(ApplicationWithPersistencePolicies, self).__init__(**kwargs)
        self.entity_persistence_policy = self.construct_entity_persistence_policy()
        self.snapshot_persistence_policy = self.construct_snapshot_persistence_policy()
        self.log_persistence_policy = self.construct_log_persistence_policy()

    def construct_entity_persistence_policy(self):
        if self.entity_event_store:
            return PersistencePolicy(
                event_store=self.entity_event_store,
                persist_event_type=VersionedEntity.Event,
            )

    def construct_snapshot_persistence_policy(self):
        if self.snapshot_event_store:
            return PersistencePolicy(
                event_store=self.snapshot_event_store,
                persist_event_type=Snapshot,
            )

    def construct_log_persistence_policy(self):
        if self.log_event_store:
            return PersistencePolicy(
                event_store=self.log_event_store,
                persist_event_type=Logged,
            )

    def close(self):
        if self.entity_persistence_policy is not None:
            self.entity_persistence_policy.close()
            self.entity_persistence_policy = None
        if self.snapshot_persistence_policy is not None:
            self.snapshot_persistence_policy.close()
            self.snapshot_persistence_policy = None
        if self.log_persistence_policy is not None:
            self.log_persistence_policy.close()
            self.log_persistence_policy = None
        super(ApplicationWithPersistencePolicies, self).close()


class ExampleApplication(ApplicationWithPersistencePolicies):
    """
    Example event sourced application with entity factory and repository.
    """

    def __init__(self, **kwargs):
        super(ExampleApplication, self).__init__(**kwargs)
        self.snapshot_strategy = None
        if self.snapshot_event_store:
            self.snapshot_strategy = EventSourcedSnapshotStrategy(
                snapshot_store=self.snapshot_event_store,
            )
        assert self.entity_event_store is not None
        self.example_repository = ExampleRepository(
            event_store=self.entity_event_store,
            snapshot_strategy=self.snapshot_strategy,
        )

    def create_new_example(self, foo='', a='', b=''):
        """Entity object factory."""
        return create_new_example(foo=foo, a=a, b=b)


def construct_example_application(**kwargs):
    """Application object factory."""
    return ExampleApplication(**kwargs)


# "Global" variable for single instance of application.
_application = None


def init_example_application(**kwargs):
    """
    Constructs single global instance of application.

    To be called when initialising a worker process.
    """
    global _application
    if _application is not None:
        raise AssertionError("init_example_application() has already been called")
    _application = construct_example_application(**kwargs)


def get_example_application():
    """
    Returns single global instance of application.

    To be called when handling a worker request, if required.
    """
    if _application is None:
        raise AssertionError("init_example_application() must be called first")
    assert isinstance(_application, ExampleApplication)
    return _application


def close_example_application():
    """
    Shuts down single global instance of application.

    To be called when tearing down, perhaps between tests, in order to allow a
    subsequent call to init_example_application().
    """
    global _application
    if _application is not None:
        _application.close()
    _application = None
