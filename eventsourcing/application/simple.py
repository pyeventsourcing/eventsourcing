import os
import zlib
from json import JSONDecoder, JSONEncoder
from typing import (
    Any,
    Dict,
    Generic,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

from eventsourcing.application.notificationlog import (
    LocalNotificationLog,
    RecordManagerNotificationLog,
)
from eventsourcing.application.pipeline import Pipeable
from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.domain.model.aggregate import BaseAggregateRoot, TAggregateEvent
from eventsourcing.domain.model.entity import (
    TDomainEvent,
    TVersionedEntity,
    TVersionedEvent,
)
from eventsourcing.domain.model.events import DomainEvent, publish
from eventsourcing.exceptions import ProgrammingError, PromptFailed
from eventsourcing.infrastructure.base import (
    DEFAULT_PIPELINE_ID,
    AbstractEventStore,
    AbstractRecordManager,
    BaseRecordManager,
    RecordManagerWithNotifications,
    RecordManagerWithTracking,
    TrackingKwargs,
)
from eventsourcing.infrastructure.datastore import AbstractDatastore
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.factory import InfrastructureFactory
from eventsourcing.infrastructure.sequenceditem import StoredEvent
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.utils.cipher.aes import AESCipher
from eventsourcing.utils.random import decode_bytes
from eventsourcing.whitehead import ActualOccasion, IterableOfEvents, T

PersistEventType = Optional[Union[Type[DomainEvent], Tuple[Type[DomainEvent]]]]

CausalDependencies = Dict[str, int]
ListOfCausalDependencies = List[CausalDependencies]


class ProcessEvent(ActualOccasion, Generic[TDomainEvent]):
    def __init__(
        self,
        domain_events: Iterable[TDomainEvent],
        tracking_kwargs: Optional[TrackingKwargs] = None,
        causal_dependencies: Optional[ListOfCausalDependencies] = None,
        orm_objs_pending_save: Sequence[Any] = (),
        orm_objs_pending_delete: Sequence[Any] = (),
    ):
        self.domain_events = domain_events
        self.tracking_kwargs = tracking_kwargs
        self.causal_dependencies = causal_dependencies
        self.orm_objs_pending_save = orm_objs_pending_save
        self.orm_objs_pending_delete = orm_objs_pending_delete


class SimpleApplication(Pipeable, Generic[TVersionedEntity, TVersionedEvent]):
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

    sequenced_item_class: Optional[Type[NamedTuple]] = None
    sequenced_item_mapper_class: Optional[Type[SequencedItemMapper]] = None
    compressor: Any = None
    json_encoder_class: Optional[Type[JSONEncoder]] = None
    sort_keys: bool = False
    json_decoder_class: Optional[Type[JSONDecoder]] = None

    persist_event_type: Optional[PersistEventType] = None
    notification_log_section_size: Optional[int] = None
    use_cache: bool = False

    event_store_class: Type[EventStore] = EventStore
    repository_class: Type[EventSourcedRepository] = EventSourcedRepository

    use_causal_dependencies = False
    set_notification_ids = False

    def __init__(
        self,
        name: str = "",
        persistence_policy: Optional[PersistencePolicy] = None,
        persist_event_type: PersistEventType = None,
        cipher_key: Optional[str] = None,
        compressor: Any = None,
        sequenced_item_class: Optional[Type[NamedTuple]] = None,
        sequenced_item_mapper_class: Optional[Type[SequencedItemMapper]] = None,
        record_manager_class: Optional[Type[AbstractRecordManager]] = None,
        stored_event_record_class: Optional[type] = None,
        event_store_class: Optional[Type[EventStore]] = None,
        snapshot_record_class: Optional[type] = None,
        setup_table: bool = True,
        contiguous_record_ids: bool = True,
        pipeline_id: int = DEFAULT_PIPELINE_ID,
        json_encoder_class: Optional[Type[JSONEncoder]] = None,
        sort_keys: bool = False,
        json_decoder_class: Optional[Type[JSONDecoder]] = None,
        notification_log_section_size: Optional[int] = None,
        use_cache: bool = False,
    ):
        """
        Initialises application object.

        :param name: Name of application.
        :param persistence_policy: Persistence policy object.
        :param persist_event_type: Tuple of domain event classes to be persisted.
        :param cipher_key: Base64 unicode string cipher key.
        :param compressor: Compressor used to compress serialized event state.
        :param sequenced_item_class: Named tuple for mapping and recording events.
        :param sequenced_item_mapper_class: Object class for mapping stored events.
        :param record_manager_class: Object class for recording stored events.
        :param stored_event_record_class: Object class for event records.
        :param event_store_class: Object class uses to store and retrieve domain events.
        :param snapshot_record_class: Object class used to represent snapshots.
        :param setup_table: Option to create database tables when application starts.
        :param contiguous_record_ids: Whether or not to delegate notification ID
            generation to the record manager (to guarantee there will be no gaps).
        :param pipeline_id: ID of instance of system pipeline expressions.
        :param json_encoder_class: Object class used to encode object as JSON strings.
        :param json_decoder_class: Object class used to decode JSON strings as objects.
        :param notification_log_section_size: Number of notification items in a section.
        :param use_cache: Whether or not to keep aggregates in memory (saves replaying
            when accessing again, but uses memory).
        """
        self.name = name or type(self).create_name()

        self.notification_log_section_size = (
            notification_log_section_size or type(self).notification_log_section_size
        )

        sequenced_item_class = sequenced_item_class or type(self).sequenced_item_class
        sequenced_item_class = sequenced_item_class or StoredEvent  # type: ignore
        self.sequenced_item_class = sequenced_item_class
        assert self.sequenced_item_class is not None
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
        self.sort_keys = sort_keys or type(self).sort_keys
        self.json_decoder_class = json_decoder_class or type(self).json_decoder_class
        self.persist_event_type = persist_event_type or type(self).persist_event_type

        self.contiguous_record_ids = contiguous_record_ids
        self.pipeline_id = pipeline_id
        self._persistence_policy = persistence_policy

        self.cipher = self.construct_cipher(cipher_key)
        self.compressor = compressor or type(self).compressor

        # Default to using zlib compression when encrypting.
        if self.cipher and self.compressor is None:
            self.compressor = zlib

        self.infrastructure_factory: Optional[
            InfrastructureFactory[TVersionedEvent]
        ] = None
        self._datastore: Optional[AbstractDatastore] = None
        self._event_store: Optional[
            AbstractEventStore[TVersionedEvent, BaseRecordManager]
        ] = None
        self._repository: Optional[
            EventSourcedRepository[TVersionedEntity, TVersionedEvent]
        ] = None
        self._notification_log: Optional[LocalNotificationLog] = None

        self.use_cache = use_cache or type(self).use_cache

        if (
            self.record_manager_class
            or self.infrastructure_factory_class.record_manager_class
        ):

            self.construct_infrastructure()

            if setup_table:
                self.setup_table()
            self.construct_notification_log()

            if self._persistence_policy is None:
                self.construct_persistence_policy()

    @classmethod
    def create_name(cls):
        return cls.__name__.lower()

    @property
    def datastore(self) -> AbstractDatastore:
        if self._datastore is None:
            self._raise_on_missing_infrastructure("datastore")
        return self._datastore

    @property
    def event_store(self) -> AbstractEventStore[TVersionedEvent, BaseRecordManager]:
        if self._event_store is None:
            self._raise_on_missing_infrastructure("event_store")
        return self._event_store

    @property
    def repository(self) -> EventSourcedRepository[TVersionedEntity, TVersionedEvent]:
        if self._repository is None:
            self._raise_on_missing_infrastructure("repository")
        return self._repository

    @property
    def notification_log(self) -> LocalNotificationLog:
        if self._notification_log is None:
            self._raise_on_missing_infrastructure("notification_log")
        return self._notification_log

    @property
    def persistence_policy(self) -> PersistencePolicy:
        if self._persistence_policy is None:
            self._raise_on_missing_infrastructure("persistence_policy")
        return self._persistence_policy

    def _raise_on_missing_infrastructure(self, what_is_missing):
        if not isinstance(self, ApplicationWithConcreteInfrastructure):
            msg = (
                "Application class %s is not an subclass of %s."
                " Try using or inheriting from or mixin() an application"
                " class with concrete infrastructure such as SQLAlchemyApplication"
                " or DjangoApplication or AxonApplication."
            ) % (type(self), ApplicationWithConcreteInfrastructure)
        else:
            msg = "Application class %s does not have a %s" % (
                type(self).__name__,
                what_is_missing,
            )
        raise ProgrammingError(msg)

    def construct_cipher(self, cipher_key_str: Optional[str]) -> Optional[AESCipher]:
        cipher_key_bytes = decode_bytes(
            cipher_key_str or os.getenv("CIPHER_KEY", "") or ""
        )
        return AESCipher(cipher_key_bytes) if cipher_key_bytes else None

    def construct_infrastructure(self, *args: Any, **kwargs: Any) -> None:
        """
        Constructs infrastructure for application.
        """
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
        Constructs infrastructure factory object.
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
            sort_keys=self.sort_keys,
            json_decoder_class=self.json_decoder_class,
            contiguous_record_ids=self.contiguous_record_ids,
            application_name=self.name,
            pipeline_id=self.pipeline_id,
            event_store_class=self.event_store_class,
            *args,
            **kwargs
        )

    def construct_datastore(self) -> None:
        """
        Constructs datastore object (used to create and drop database tables).
        """
        assert self.infrastructure_factory
        self._datastore = self.infrastructure_factory.construct_datastore()

    def construct_event_store(self) -> None:
        """
        Constructs event store object.
        """
        assert self.infrastructure_factory
        factory = self.infrastructure_factory
        self._event_store = factory.construct_integer_sequenced_event_store(
            self.cipher, self.compressor
        )

    def construct_repository(self, **kwargs: Any) -> None:
        """
        Constructs repository object.
        """
        assert self.repository_class
        self._repository = self.repository_class(
            event_store=self.event_store, use_cache=self.use_cache, **kwargs
        )

    def setup_table(self) -> None:
        """
        Sets up the database table using event store's record class.
        """
        if self._datastore is not None:
            record_class = self.event_store.record_manager.record_class
            self.datastore.setup_table(record_class)

    def drop_table(self) -> None:
        """
        Drops the database table using event store's record class.
        """
        if self._datastore is not None:
            record_class = self.event_store.record_manager.record_class
            self.datastore.drop_table(record_class)

    def construct_notification_log(self) -> None:
        """
        Constructs notification log object.
        """
        self._notification_log = RecordManagerNotificationLog(
            self.event_store.record_manager,
            section_size=self.notification_log_section_size,
        )

    def construct_persistence_policy(self) -> None:
        """
        Constructs persistence policy object.
        """
        self._persistence_policy = PersistencePolicy(
            event_store=self.event_store, persist_event_type=self.persist_event_type
        )

    def change_pipeline(self, pipeline_id: int) -> None:
        """
        Switches pipeline being used by this application object.
        """
        self.pipeline_id = pipeline_id
        self.event_store.record_manager.pipeline_id = pipeline_id

    def close(self) -> None:
        """
        Closes the application for further use.

        The persistence policy is closed, and the application's
        connection to the database is closed.
        """
        # Close the persistence policy.
        if self._persistence_policy is not None:
            self._persistence_policy.close()

        # Close database connection.
        if self._datastore is not None:
            self._datastore.close_connection()

    def __enter__(self: T) -> T:
        """
        Supports use of application as context manager.
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Closes application when exiting context manager.
        """
        self.close()

    @classmethod
    def reset_connection_after_forking(cls) -> None:
        pass

    @classmethod
    def mixin(cls: T, infrastructure_class: type) -> T:
        """
        Returns subclass that inherits also from given infrastructure class.
        """
        return type(cls.__name__, (infrastructure_class, cls), {})

    def save(
        self, aggregates=(), orm_objects_pending_save=(), orm_objects_pending_delete=(),
    ) -> None:
        """
        Saves state of aggregates, and ORM objects.

        All of the pending events of the aggregates, along with the
        ORM objects, are recorded atomically as a process event.

        Then a "prompt to pull" is published, and, if the repository cache
        is in use, then puts the aggregates in the cache.

        :param aggregates: One or many aggregates.
        :param orm_objects_pending_save: Sequence of ORM objects to be saved.
        :param orm_objects_pending_delete: Sequance of ORM objects to be deleted.
        """
        # Collect pending events from the aggregates.
        new_events = []
        if isinstance(aggregates, BaseAggregateRoot):
            aggregates = [aggregates]
        else:
            pass
            # Todo: Make sure record manager supports writing events from more than
            #  one aggregate atomically (e.g. Cassandra and EventStore don't).

        for aggregate in aggregates:
            new_events += aggregate.__batch_pending_events__()
        process_event = ProcessEvent(
            domain_events=new_events,
            orm_objs_pending_save=orm_objects_pending_save,
            orm_objs_pending_delete=orm_objects_pending_delete,
        )
        new_records = self.record_process_event(process_event)
        record_manager = self.event_store.record_manager
        if isinstance(record_manager, RecordManagerWithNotifications):
            # Find the head notification ID.
            notifiable_events = [e for e in new_events if e.__notifiable__]
            head_notification_id = None
            if len(notifiable_events):
                notification_id_name = record_manager.notification_id_name
                notifications = []
                for record in new_records:
                    if not hasattr(record, notification_id_name):
                        continue
                    if not isinstance(getattr(record, notification_id_name), int):
                        continue
                    notifications.append(
                        record_manager.create_notification_from_record(record)
                    )

                if len(notifications):
                    head_notification_id = notifications[-1]["id"]
            self.publish_prompt(head_notification_id)
        if self.repository.use_cache:
            for aggregate in aggregates:
                self.repository.put_entity_in_cache(aggregate.id, aggregate)

    def record_process_event(self, process_event: ProcessEvent) -> List:
        """
        Records a process event.

        Converts the domain events of the process event to event record
        objects, and writes the event records and the ORM objects to
        the database using the application's event store's record manager.

        :param process_event: An instance of
            :class:`~eventsourcing.application.simple.ProcessEvent`
        :return: A list of event records.
        """
        # Construct event records.
        event_records = self.construct_event_records(
            process_event.domain_events, process_event.causal_dependencies
        )

        # Write event records with tracking record.
        record_manager = self.event_store.record_manager
        assert isinstance(record_manager, RecordManagerWithTracking)
        record_manager.write_records(
            records=event_records,
            tracking_kwargs=process_event.tracking_kwargs,
            orm_objs_pending_save=process_event.orm_objs_pending_save,
            orm_objs_pending_delete=process_event.orm_objs_pending_delete,
        )
        return event_records

    def construct_event_records(
        self,
        pending_events: Iterable[TAggregateEvent],
        causal_dependencies: Optional[ListOfCausalDependencies],
    ) -> List:
        """
        Constructs event records from domain events.

        :param pending_events: An iterable of domain events.
        :param causal_dependencies: A list of causal dependencies.
        :return: A list of event records.
        """
        # Convert to event records.
        sequenced_items = self.event_store.items_from_events(pending_events)
        record_manager = self.event_store.record_manager
        assert record_manager
        assert isinstance(record_manager, RecordManagerWithTracking)
        event_records = list(record_manager.to_records(sequenced_items))

        # Set notification log IDs, and causal dependencies.
        if len(event_records):
            # Todo: Maybe keep track of what this probably is, to
            #  avoid query. Like log reader, invalidate on error.
            if self.set_notification_ids:
                notification_id_name = record_manager.notification_id_name
                current_max = record_manager.get_max_notification_id()
                for domain_event, event_record in zip(pending_events, event_records):
                    if type(domain_event).__notifiable__:
                        current_max += 1
                        setattr(event_record, notification_id_name, current_max)
                    else:
                        setattr(
                            event_record, notification_id_name, "event-not-notifiable"
                        )
            else:
                if any((not e.__notifiable__ for e in pending_events)):
                    raise Exception(
                        "Can't set __notifiable__=False without "
                        "set_notification_ids=True "
                    )

            if self.use_causal_dependencies:
                assert hasattr(record_manager.record_class, "causal_dependencies")
                causal_dependencies_json = self.event_store.event_mapper.json_dumps(
                    causal_dependencies
                ).decode("utf8")
                # Only need first event to carry the dependencies.
                event_records[0].causal_dependencies = causal_dependencies_json

        return event_records

    def publish_prompt(self, head_notification_id=None):
        """
        Publishes a "prompt to pull" (instance of
        :class:`~eventsourcing.application.simple.PromptToPull`).

        :param head_notification_id: Maximum notification ID of event records
            to be pulled.
        """
        prompt = PromptToPull(self.name, self.pipeline_id, head_notification_id)
        try:
            publish(prompt)
        except PromptFailed:
            raise
        except Exception as e:
            raise PromptFailed("{}: {}".format(type(e), str(e)))


class ApplicationWithConcreteInfrastructure(SimpleApplication):
    """
    Base class for application classes that have actual infrastructure.
    """


class Prompt(ActualOccasion):
    pass


def is_prompt_to_pull(events: IterableOfEvents) -> bool:
    return isinstance(events, PromptToPull)


class PromptToPull(Prompt):
    def __init__(self, process_name: str, pipeline_id: int, head_notification_id=None):
        self.process_name: str = process_name
        self.pipeline_id: int = pipeline_id
        self.head_notification_id = head_notification_id

    def __eq__(self, other: object) -> bool:
        return bool(
            other
            and isinstance(other, type(self))
            and self.process_name == other.process_name
            and self.pipeline_id == other.pipeline_id
        )

    def __repr__(self) -> str:
        return "{}({}={}, {}={})".format(
            type(self).__name__,
            "process_name",
            self.process_name,
            "pipeline_id",
            self.pipeline_id,
        )
