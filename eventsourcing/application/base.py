from abc import ABCMeta

from six import with_metaclass

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.entity import VersionedEntity
from eventsourcing.domain.model.events import Logged
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.utils.transcoding import ObjectJSONDecoder, ObjectJSONEncoder


class ApplicationWithEventStores(with_metaclass(ABCMeta)):
    """
    Event sourced application object class.

    Can construct event stores using given database records.
    Supports three different event stores: for log events,
    for entity events, and for snapshot events.
    """
    def __init__(self, entity_record_manager=None,
                 log_record_manager=None,
                 snapshot_record_manager=None,
                 always_encrypt=False, cipher=None):

        self.entity_event_store = None
        if entity_record_manager:
            self.entity_event_store = self.construct_event_store(
                event_sequence_id_attr='originator_id',
                event_position_attr='originator_version',
                record_manager=entity_record_manager,
                always_encrypt=always_encrypt,
                cipher=cipher,
            )

        self.log_event_store = None
        if log_record_manager:
            self.log_event_store = self.construct_event_store(
                event_sequence_id_attr='originator_id',
                event_position_attr='timestamp',
                record_manager=log_record_manager,
                always_encrypt=always_encrypt,
                cipher=cipher,
            )

        self.snapshot_event_store = None
        if snapshot_record_manager:
            self.snapshot_event_store = self.construct_event_store(
                event_sequence_id_attr='originator_id',
                event_position_attr='originator_version',
                record_manager=snapshot_record_manager,
                always_encrypt=always_encrypt,
                cipher=cipher,
            )

    def construct_event_store(self, event_sequence_id_attr, event_position_attr, record_manager,
                              always_encrypt=False, cipher=None):
        sequenced_item_mapper = self.construct_sequenced_item_mapper(
            sequenced_item_class=record_manager.sequenced_item_class,
            event_sequence_id_attr=event_sequence_id_attr,
            event_position_attr=event_position_attr,
            always_encrypt=always_encrypt,
            cipher=cipher,
        )
        event_store = EventStore(
            record_manager=record_manager,
            sequenced_item_mapper=sequenced_item_mapper,
        )
        return event_store

    def construct_sequenced_item_mapper(self, sequenced_item_class, event_sequence_id_attr, event_position_attr,
                                        json_encoder_class=ObjectJSONEncoder, json_decoder_class=ObjectJSONDecoder,
                                        always_encrypt=False, cipher=None):
        return SequencedItemMapper(
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
                event_type=VersionedEntity.Event,
            )

    def construct_snapshot_persistence_policy(self):
        if self.snapshot_event_store:
            return PersistencePolicy(
                event_store=self.snapshot_event_store,
                event_type=Snapshot,
            )

    def construct_log_persistence_policy(self):
        if self.log_event_store:
            return PersistencePolicy(
                event_store=self.log_event_store,
                event_type=Logged,
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
