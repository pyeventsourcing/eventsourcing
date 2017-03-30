from abc import ABCMeta

from six import with_metaclass

from eventsourcing.application.policies import CombinedPersistencePolicy
from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.infrastructure.transcoding import ObjectJSONEncoder, ObjectJSONDecoder


class ReadOnlyEventSourcingApplication(with_metaclass(ABCMeta)):
    def __init__(self, integer_sequenced_active_record_strategy=None,
                 timestamp_sequenced_active_record_strategy=None, always_encrypt=False, cipher=None):
        """
        Constructs an event store using the given stored event repository.

        :param: sequenced_item_repository:  Repository containing sequenced items.

        :param always_encrypt:  Optional encryption of persisted state.

        :param cipher:  Used to encrypt and decrypt stored events.

        """
        assert isinstance(integer_sequenced_active_record_strategy, AbstractActiveRecordStrategy), \
            type(integer_sequenced_active_record_strategy)

        assert isinstance(timestamp_sequenced_active_record_strategy, AbstractActiveRecordStrategy), \
            type(integer_sequenced_active_record_strategy)

        self.integer_sequenced_active_record_strategy = integer_sequenced_active_record_strategy
        self.timestamp_sequenced_active_record_strategy = timestamp_sequenced_active_record_strategy
        self.version_entity_event_store = self.construct_event_store(
            event_sequence_id_attr='entity_id',
            event_position_attr='entity_version',
            active_record_strategy=self.integer_sequenced_active_record_strategy,
            always_encrypt=always_encrypt,
            cipher=cipher,
        )
        self.timestamp_entity_event_store = self.construct_event_store(
            event_sequence_id_attr='entity_id',
            event_position_attr='timestamp',
            active_record_strategy=self.timestamp_sequenced_active_record_strategy,
            always_encrypt=always_encrypt,
            cipher=cipher,
        )

    def construct_event_store(self, event_sequence_id_attr, event_position_attr, active_record_strategy,
                              always_encrypt=False, cipher=None):
        sequenced_item_mapper = self.construct_sequenced_item_mapper(
            sequenced_item_class=active_record_strategy.sequenced_item_class,
            event_sequence_id_attr=event_sequence_id_attr,
            event_position_attr=event_position_attr,
            always_encrypt=always_encrypt,
            cipher=cipher
        )
        event_store = EventStore(
            active_record_strategy=active_record_strategy,
            sequenced_item_mapper=sequenced_item_mapper,
        )
        return event_store

    def construct_sequenced_item_mapper(self, sequenced_item_class, event_sequence_id_attr, event_position_attr,
                                        json_encoder_class=ObjectJSONEncoder, json_decoder_class=ObjectJSONDecoder,
                                        always_encrypt=False, cipher=None):
        return SequencedItemMapper(
            sequenced_item_class=sequenced_item_class,
            event_sequence_id_attr=event_sequence_id_attr,
            event_position_attr=event_position_attr,
            json_encoder_class=json_encoder_class,
            json_decoder_class=json_decoder_class,
            always_encrypt=always_encrypt,
            cipher=cipher
        )

    def close(self):
        self.event_store = None
        self.integer_sequenced_active_record_strategy = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class EventSourcedApplication(ReadOnlyEventSourcingApplication):
    def __init__(self, **kwargs):
        super(EventSourcedApplication, self).__init__(**kwargs)
        self.persistence_policy = self.construct_persistence_policy()

    def construct_persistence_policy(self):
        return CombinedPersistencePolicy(
            versioned_entity_event_store=self.version_entity_event_store,
            timestamped_entity_event_store=self.timestamp_entity_event_store,
        )

    def close(self):
        if self.persistence_policy is not None:
            self.persistence_policy.close()
            self.persistence_policy = None
        super(EventSourcedApplication, self).close()
