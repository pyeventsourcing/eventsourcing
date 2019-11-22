import os
from json import JSONEncoder, JSONDecoder
from typing import Any, Generic, Optional, Tuple, Type, Union

from eventsourcing.application.notificationlog import RecordManagerNotificationLog
from eventsourcing.application.pipeline import Pipeable
from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.infrastructure.base import BaseRecordManager, DEFAULT_PIPELINE_ID
from eventsourcing.infrastructure.datastore import AbstractDatastore
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.factory import InfrastructureFactory
from eventsourcing.infrastructure.sequenceditem import StoredEvent
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.types import AbstractRecordManager, T_aen, T_aev, T
from eventsourcing.utils.cipher.aes import AESCipher
from eventsourcing.utils.random import decode_bytes


PersistEventType = Optional[Union[Type[DomainEvent], Tuple[Type[DomainEvent]]]]


class SimpleApplication(Pipeable, Generic[T_aen, T_aev]):
    """
    Base class for event sourced applications.

    Constructs infrastructure objects such as the repository and
    event store, and also the notification log which presents the
    application state as a sequence of events.

    Needs actual infrastructure classes.
    """

    infrastructure_factory_class: Type[InfrastructureFactory] = InfrastructureFactory
    is_constructed_with_session: bool = False

    record_manager_class: Optional[Type[AbstractRecordManager]] = None
    stored_event_record_class: Optional[type] = None
    snapshot_record_class: Optional[type] = None

    sequenced_item_class: Optional[type] = None
    sequenced_item_mapper_class: Optional[Type[SequencedItemMapper]] = None
    json_encoder_class: Optional[type] = None
    json_decoder_class: Optional[type] = None

    persist_event_type: Optional[PersistEventType] = None
    notification_log_section_size: Optional[int] = None
    use_cache: bool = False

    event_store_class: Type[EventStore] = EventStore
    repository_class: Type[EventSourcedRepository] = EventSourcedRepository

    def __init__(
        self,
        name: str = "",
        persistence_policy: Optional[PersistencePolicy] = None,
        persist_event_type: PersistEventType = None,
        cipher_key: Optional[str] = None,
        sequenced_item_class: Optional[Type[Tuple]] = None,
        sequenced_item_mapper_class: Optional[Type[SequencedItemMapper]] = None,
        record_manager_class: Optional[Type[AbstractRecordManager]] = None,
        stored_event_record_class: Optional[type] = None,
        event_store_class: Optional[Type[EventStore]] = None,
        snapshot_record_class: Optional[type] = None,
        setup_table: bool = True,
        contiguous_record_ids: bool = True,
        pipeline_id: int = DEFAULT_PIPELINE_ID,
        json_encoder_class: Optional[Type[JSONEncoder]] = None,
        json_decoder_class: Optional[Type[JSONDecoder]] = None,
        notification_log_section_size: Optional[int] = None,
    ):
        self.name = name or type(self).__name__.lower()

        self.notification_log_section_size = notification_log_section_size

        self.sequenced_item_class = (
            sequenced_item_class or type(self).sequenced_item_class or StoredEvent
        )

        self.sequenced_item_mapper_class: Type[SequencedItemMapper] = (
            sequenced_item_mapper_class
            or type(self).sequenced_item_mapper_class
            or SequencedItemMapper
        )

        self.record_manager_class = (
            record_manager_class or type(self).record_manager_class
        )
        self._stored_event_record_class = stored_event_record_class
        self._snapshot_record_class = snapshot_record_class

        self.event_store_class = event_store_class or type(self).event_store_class

        self.json_encoder_class = json_encoder_class or type(self).json_encoder_class
        self.json_decoder_class = json_decoder_class or type(self).json_decoder_class
        self.persist_event_type = persist_event_type or type(self).persist_event_type

        self.contiguous_record_ids = contiguous_record_ids
        self.pipeline_id = pipeline_id
        self.persistence_policy = persistence_policy

        self.cipher = self.construct_cipher(cipher_key)

        self.infrastructure_factory: Optional[InfrastructureFactory] = None
        self._datastore: Optional[AbstractDatastore] = None
        self._event_store: Optional[EventStore] = None
        self._repository: Optional[EventSourcedRepository] = None

        if (
            self.record_manager_class
            or self.infrastructure_factory_class.record_manager_class
        ):

            self.construct_infrastructure()

            if setup_table:
                self.setup_table()
            self.construct_notification_log()

            if self.persistence_policy is None:
                self.construct_persistence_policy()

    @property
    def datastore(self) -> AbstractDatastore:
        assert self._datastore
        return self._datastore

    @property
    def session(self) -> Optional[Any]:
        return None

    @property
    def event_store(self) -> EventStore[T_aev, BaseRecordManager[T_aev]]:
        assert self._event_store
        return self._event_store

    @property
    def repository(self) -> EventSourcedRepository[T_aen, T_aev]:
        assert self._repository
        return self._repository

    def construct_cipher(self, cipher_key_str: Optional[str]) -> Optional[AESCipher]:
        cipher_key_bytes = decode_bytes(
            cipher_key_str or os.getenv("CIPHER_KEY", "") or ""
        )
        return AESCipher(cipher_key_bytes) if cipher_key_bytes else None

    def construct_infrastructure(self, *args: Any, **kwargs: Any) -> None:
        self.infrastructure_factory = self.construct_infrastructure_factory(
            *args, **kwargs
        )
        self.construct_datastore()
        self.construct_event_store()
        self.construct_repository()

    def construct_infrastructure_factory(
        self, *args: Any, **kwargs: Any
    ) -> InfrastructureFactory:
        """
        :rtype: InfrastructureFactory
        """
        factory_class = self.infrastructure_factory_class
        assert issubclass(factory_class, InfrastructureFactory)

        integer_sequenced_record_class = (
            self._stored_event_record_class or self.stored_event_record_class
        )
        snapshot_record_class = (
            self._snapshot_record_class or self.snapshot_record_class
        )

        return factory_class(  # type:ignore  # multiple values for keyword argument
            record_manager_class=self.record_manager_class,
            integer_sequenced_record_class=integer_sequenced_record_class,
            snapshot_record_class=snapshot_record_class,
            sequenced_item_class=self.sequenced_item_class,
            sequenced_item_mapper_class=self.sequenced_item_mapper_class,
            json_encoder_class=self.json_encoder_class,
            json_decoder_class=self.json_decoder_class,
            contiguous_record_ids=self.contiguous_record_ids,
            application_name=self.name,
            pipeline_id=self.pipeline_id,
            event_store_class=self.event_store_class,
            *args,
            **kwargs
        )

    def construct_datastore(self) -> None:
        assert self.infrastructure_factory
        self._datastore = self.infrastructure_factory.construct_datastore()

    def construct_event_store(self) -> None:
        assert self.infrastructure_factory
        factory = self.infrastructure_factory
        self._event_store = factory.construct_integer_sequenced_event_store(self.cipher)

    def construct_repository(self, **kwargs: Any) -> None:
        assert self.repository_class
        self._repository = self.repository_class(
            event_store=self.event_store, use_cache=self.use_cache, **kwargs
        )

    def setup_table(self) -> None:
        # Setup the database table using event store's record class.
        if self._datastore is not None:
            assert self.event_store
            record_class = self.event_store.record_manager.record_class
            self.datastore.setup_table(record_class)

    def drop_table(self) -> None:
        # Drop the database table using event store's record class.
        if self._datastore is not None:
            assert self.event_store
            record_class = self.event_store.record_manager.record_class
            self.datastore.drop_table(record_class)

    def construct_notification_log(self) -> None:
        assert self.event_store
        self.notification_log = RecordManagerNotificationLog(
            self.event_store.record_manager,
            section_size=self.notification_log_section_size,
        )

    def construct_persistence_policy(self) -> None:
        assert self.event_store
        self.persistence_policy = PersistencePolicy(
            event_store=self.event_store, persist_event_type=self.persist_event_type
        )

    def change_pipeline(self, pipeline_id: int) -> None:
        self.pipeline_id = pipeline_id
        assert self.event_store
        assert self.event_store.record_manager
        self.event_store.record_manager.pipeline_id = pipeline_id

    def close(self) -> None:
        # Close the persistence policy.
        if self.persistence_policy is not None:
            self.persistence_policy.close()

        # Close database connection.
        if self._datastore is not None:
            self._datastore.close_connection()

    def __enter__(self: T) -> T:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    @classmethod
    def reset_connection_after_forking(cls) -> None:
        pass

    @classmethod
    def mixin(cls, infrastructure_class: type) -> type:
        return type(cls.__name__, (infrastructure_class, cls), {})


class ApplicationWithConcreteInfrastructure(SimpleApplication):
    """
    Subclasses have actual infrastructure.
    """
