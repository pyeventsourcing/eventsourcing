import os
from abc import ABCMeta

from six import with_metaclass

from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.infrastructure.base import DEFAULT_PIPELINE_ID
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.factory import InfrastructureFactory
from eventsourcing.infrastructure.sequenceditem import StoredEvent
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.interface.notificationlog import RecordManagerNotificationLog
from eventsourcing.utils.cipher.aes import AESCipher
from eventsourcing.utils.random import decode_bytes


class SimpleApplication(with_metaclass(ABCMeta)):
    """
    Sets up infrastructure for use
    with an event sourced domain model.
    """

    infrastructure_factory_class = InfrastructureFactory
    is_constructed_with_session = False

    record_manager_class = None
    stored_event_record_class = None
    snapshot_record_class = None

    sequenced_item_class = None
    sequenced_item_mapper_class = None
    json_encoder_class = None
    json_decoder_class = None

    persist_event_type = None
    notification_log_section_size = None
    use_cache = False

    event_store_class = EventStore
    repository_class = EventSourcedRepository

    def __init__(self, name='', persistence_policy=None, persist_event_type=None,
                 cipher_key=None, sequenced_item_class=None, sequenced_item_mapper_class=None,
                 record_manager_class=None, stored_event_record_class=None,
                 snapshot_record_class=None, setup_table=True, contiguous_record_ids=True,
                 pipeline_id=DEFAULT_PIPELINE_ID, json_encoder_class=None,
                 json_decoder_class=None, notification_log_section_size=None):

        self.name = name or type(self).__name__.lower()

        self.notification_log_section_size = notification_log_section_size

        self.sequenced_item_class = sequenced_item_class \
                                    or type(self).sequenced_item_class \
                                    or StoredEvent

        self.sequenced_item_mapper_class = sequenced_item_mapper_class \
                                           or type(self).sequenced_item_mapper_class \
                                           or SequencedItemMapper

        self.record_manager_class = record_manager_class or type(self).record_manager_class

        self.stored_event_record_class = stored_event_record_class or type(self).stored_event_record_class

        self.snapshot_record_class = snapshot_record_class or type(self).snapshot_record_class

        self.json_encoder_class = json_encoder_class or type(self).json_encoder_class

        self.json_decoder_class = json_decoder_class or type(self).json_decoder_class

        self.persist_event_type = persist_event_type or type(self).persist_event_type

        self.contiguous_record_ids = contiguous_record_ids
        self.pipeline_id = pipeline_id
        self.setup_cipher(cipher_key)
        self.setup_infrastructure()
        if setup_table:
            self.setup_table()
        self.setup_notification_log()

        self.persistence_policy = persistence_policy
        if self.persistence_policy is None:
            self.setup_persistence_policy()

    @property
    def datastore(self):
        return self._datastore

    @property
    def event_store(self):
        return self._event_store

    @property
    def repository(self):
        return self._repository

    def setup_cipher(self, cipher_key):
        cipher_key = decode_bytes(cipher_key or os.getenv('CIPHER_KEY', ''))
        self.cipher = AESCipher(cipher_key) if cipher_key else None

    def setup_infrastructure(self, *args, **kwargs):
        self.infrastructure_factory = self.construct_infrastructure_factory(*args, **kwargs)
        self.setup_datastore()
        self.setup_event_store()
        self.setup_repository()

    def setup_datastore(self):
        self._datastore = self.infrastructure_factory.construct_datastore()

    def construct_infrastructure_factory(self, *args, **kwargs):
        """
        :rtype: InfrastructureFactory
        """
        factory_class = self.infrastructure_factory_class
        assert issubclass(factory_class, InfrastructureFactory)
        return factory_class(
            record_manager_class=self.record_manager_class,
            integer_sequenced_record_class=self.stored_event_record_class,
            sequenced_item_class=self.sequenced_item_class,
            contiguous_record_ids=self.contiguous_record_ids,
            application_name=self.name,
            pipeline_id=self.pipeline_id,
            snapshot_record_class=self.snapshot_record_class,
            *args, **kwargs
        )

    def setup_event_store(self):
        # Construct event store.
        sequenced_item_mapper = self.sequenced_item_mapper_class(
            sequenced_item_class=self.sequenced_item_class,
            cipher=self.cipher,
            # sequence_id_attr_name=sequence_id_attr_name,
            # position_attr_name=position_attr_name,
            json_encoder_class=self.json_encoder_class,
            json_decoder_class=self.json_decoder_class,
        )
        record_manager = self.infrastructure_factory.construct_integer_sequenced_record_manager()
        self._event_store = self.event_store_class(
            record_manager=record_manager,
            sequenced_item_mapper=sequenced_item_mapper,
        )

    def setup_repository(self, **kwargs):
        self._repository = self.repository_class(
            event_store=self.event_store,
            use_cache=self.use_cache,
            **kwargs
        )

    def setup_table(self):
        # Setup the database table using event store's record class.
        if self.datastore is not None:
            self.datastore.setup_table(
                self.event_store.record_manager.record_class
            )

    def drop_table(self):
        # Drop the database table using event store's record class.
        if self.datastore is not None:
            self.datastore.drop_table(
                self.event_store.record_manager.record_class
            )

    def setup_notification_log(self):
        self.notification_log = RecordManagerNotificationLog(
            self.event_store.record_manager,
            section_size=self.notification_log_section_size
        )

    def setup_persistence_policy(self):
        self.persistence_policy = PersistencePolicy(
            event_store=self.event_store,
            event_type=self.persist_event_type
        )

    def change_pipeline(self, pipeline_id):
        self.pipeline_id = pipeline_id
        self.event_store.record_manager.pipeline_id = pipeline_id

    def close(self):
        # Close the persistence policy.
        if self.persistence_policy is not None:
            self.persistence_policy.close()

        # Close database connection.
        if self.datastore is not None:
            self.datastore.close_connection()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @classmethod
    def mixin(cls, *bases):
        return type(cls.__name__, bases + (cls,), {})


class Application(SimpleApplication):
    pass
