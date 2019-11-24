from abc import ABC, abstractmethod
from typing import (
    Any,
    Generic,
    Iterable,
    Iterator,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)
from uuid import UUID

from eventsourcing.exceptions import OperationalError, RecordConflictError
from eventsourcing.infrastructure.sequenceditem import (
    SequencedItem,
    SequencedItemFieldNames,
)
from eventsourcing.whitehead import (
    ActualOccasion,
    TEvent,
    OneOrManyEvents,
    SequenceOfEvents,
    TEntity,
)

DEFAULT_PIPELINE_ID = 0


class AbstractRecordManager(ABC, Generic[TEvent]):
    @property
    @abstractmethod
    def record_class(self) -> Any:
        pass

    @abstractmethod
    def record_sequenced_items(
        self, sequenced_item_or_items: Union[Sequence[Tuple], Tuple]
    ) -> None:
        """
        Writes sequenced item(s) into the datastore.
        """

    @abstractmethod
    def get_item(self, sequence_id: UUID, position: int) -> Tuple:
        """
        Gets sequenced item from the datastore.
        """

    @abstractmethod
    def get_items(
        self,
        sequence_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        query_ascending: bool = True,
        results_ascending: bool = True,
    ) -> Iterator[SequenceOfEvents]:
        """
        Iterates over records in sequence.
        """

    @abstractmethod
    def get_record(self, sequence_id: UUID, position: int) -> Any:
        """
        Gets record at position in sequence.
        """

    @abstractmethod
    def get_records(
        self,
        sequence_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        query_ascending: bool = True,
        results_ascending: bool = True,
    ) -> Sequence[Any]:
        """
        Returns records for a sequence.
        """

    @abstractmethod
    def get_notifications(
        self,
        start: Optional[int] = None,
        stop: Optional[int] = None,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """
        Returns records sequenced by notification ID, from
        application, for pipeline, in given range.

        Args 'start' and 'stop' are positions in a zero-based
        integer sequence.
        """

    @abstractmethod
    def all_sequence_ids(self) -> Sequence[UUID]:
        """
        Returns all sequence IDs.
        """

    @abstractmethod
    def delete_record(self, record: Any) -> None:
        """
        Removes permanently given record from the table.
        """


TRecordManager = TypeVar("TRecordManager", bound=AbstractRecordManager)


class BaseRecordManager(AbstractRecordManager[TEvent]):
    def __init__(
        self,
        record_class,
        sequenced_item_class=SequencedItem,
        contiguous_record_ids=False,
        application_name=None,
        pipeline_id=DEFAULT_PIPELINE_ID,
    ):
        self._record_class = record_class
        self.sequenced_item_class = sequenced_item_class
        self.field_names = SequencedItemFieldNames(self.sequenced_item_class)

        if hasattr(self.record_class, "id"):
            self.notification_id_name = "id"
        elif hasattr(self.record_class, "notification_id"):
            self.notification_id_name = "notification_id"
        else:
            self.notification_id_name = ""

        self.contiguous_record_ids = contiguous_record_ids and self.notification_id_name
        if hasattr(self.record_class, "application_name"):
            assert application_name, "'application_name' not set when required"
            assert (
                contiguous_record_ids
            ), "'contiguous_record_ids' not set when required"
        self.application_name = application_name
        if hasattr(self.record_class, "pipeline_id"):
            assert hasattr(
                self.record_class, "application_name"
            ), "'application_name' column not defined"
        self.pipeline_id = pipeline_id

    @property
    def record_class(self):
        return self._record_class

    def clone(self, application_name, pipeline_id, **kwargs):
        return type(self)(
            record_class=self.record_class,
            contiguous_record_ids=self.contiguous_record_ids,
            sequenced_item_class=self.sequenced_item_class,
            application_name=application_name,
            pipeline_id=pipeline_id,
            **kwargs
        )

    def record_sequenced_item(self, sequenced_item):
        """
        Writes sequenced item into the datastore.
        """
        return self.record_sequenced_items(sequenced_item)

    def get_item(self, sequence_id: UUID, position: int) -> Tuple:
        """
        Gets sequenced item from the datastore.
        """
        return self.from_record(self.get_record(sequence_id, position))

    def get_items(
        self,
        sequence_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        query_ascending: bool = True,
        results_ascending: bool = True,
    ) -> Iterator[SequenceOfEvents]:
        """
        Returns sequenced item generator.
        """
        records = self.get_records(
            sequence_id=sequence_id,
            gt=gt,
            gte=gte,
            lt=lt,
            lte=lte,
            limit=limit,
            query_ascending=query_ascending,
            results_ascending=results_ascending,
        )
        for item in map(self.from_record, records):
            yield item

    def list_items(self, *args, **kwargs):
        """
        Returns list of sequenced items.
        """
        return list(self.get_items(*args, **kwargs))

    def to_record(self, sequenced_item):
        """
        Constructs a record object from given sequenced item object.
        """
        kwargs = self.get_field_kwargs(sequenced_item)
        # Supply application_name, if needed.
        if hasattr(self.record_class, "application_name"):
            kwargs["application_name"] = self.application_name
        # Supply pipeline_id, if needed.
        if hasattr(self.record_class, "pipeline_id"):
            kwargs["pipeline_id"] = self.pipeline_id
        return self.record_class(**kwargs)

    def from_record(self, record: Any) -> Tuple:
        """
        Constructs and returns a sequenced item object, from given ORM object.
        """
        kwargs = self.get_field_kwargs(record)
        return self.sequenced_item_class(**kwargs)

    def list_sequence_ids(self):
        return list(self.all_sequence_ids())

    def get_field_kwargs(self, item):
        return {name: getattr(item, name) for name in self.field_names}

    def raise_sequenced_item_conflict(self):
        msg = "Position already taken in sequence"
        raise RecordConflictError(msg)

    def raise_index_error(self, position):
        raise IndexError("Sequence index out of range: {}".format(position))

    def raise_record_integrity_error(self, e):
        raise RecordConflictError(e)

    def raise_operational_error(self, e):
        raise OperationalError(e)


class ACIDRecordManager(BaseRecordManager[TEvent]):
    """
    ACID record managers can write tracking records and event records
    in an atomic transaction, needed for atomic processing in process
    applications.
    """

    tracking_record_field_names = [
        "application_name",
        "upstream_application_name",
        "pipeline_id",
        "notification_id",
    ]

    def __init__(self, tracking_record_class=None, *args, **kwargs):
        super(ACIDRecordManager, self).__init__(*args, **kwargs)
        # assert tracking_record_class is not None
        self.tracking_record_class = tracking_record_class

    def clone(self, **kwargs):
        return super(ACIDRecordManager, self).clone(
            tracking_record_class=self.tracking_record_class, **kwargs
        )

    @abstractmethod
    def write_records(
        self,
        records,
        tracking_kwargs=None,
        orm_objs_pending_save=None,
        orm_objs_pending_delete=None,
    ):
        """
        Writes tracking, event and notification records for a process event.
        :param orm_objs_pending_delete:
        :param orm_objs_pending_save:
        """

    def to_records(self, sequenced_item_or_items):
        if isinstance(sequenced_item_or_items, list):
            records = [self.to_record(i) for i in sequenced_item_or_items]
        else:
            records = [self.to_record(sequenced_item_or_items)]
        return records

    @abstractmethod
    def get_max_record_id(self) -> int:
        """Return maximum notification ID in pipeline."""

    @abstractmethod
    def get_max_tracking_record_id(self, upstream_application_name: str) -> int:
        """Return maximum tracking record ID for notification from upstream
        application in pipeline."""

    @abstractmethod
    def has_tracking_record(
        self, upstream_application_name: str, pipeline_id: int, notification_id: int
    ) -> bool:
        """
        True if tracking record exists for notification from upstream in pipeline.
        """

    def get_pipeline_and_notification_id(self, sequence_id, position: int) -> Tuple:
        """
        Returns pipeline ID and notification ID for
        event at given position in given sequence.
        """
        # Todo: Optimise query by selecting only two columns,
        #  pipeline_id and id (notification ID)?
        record = self.get_record(sequence_id, position)
        notification_id = getattr(record, self.notification_id_name)
        return record.pipeline_id, notification_id


class SQLRecordManager(ACIDRecordManager):
    """
    Common aspects of SQL record managers, such as SQLAlchemy and Django record
    managers.
    """

    # Todo: This makes the subclasses harder to read and probably more brittle. So it
    #  might be better to inline this with the subclasses, so that each looks more
    #  like normal Django or SQLAlchemy code.
    # Todo: Also, the record manager test cases don't cover the notification log and
    #  tracking record functionality needed by ProcessApplication, and should so
    #  that other record managers can more easily be developed.

    def __init__(self, *args, **kwargs):
        super(SQLRecordManager, self).__init__(*args, **kwargs)
        self._insert_select_max = None
        self._insert_values = None
        self._insert_tracking_record = None

    def record_sequenced_items(self, sequenced_item_or_items):
        # Convert sequenced item(s) to database record(s).
        records = self.to_records(sequenced_item_or_items)

        # Write records.
        self.write_records(records)

    @property
    def insert_select_max(self):
        """
        SQL statement that inserts records with contiguous IDs,
        by selecting max ID from indexed table records.
        """
        if self._insert_select_max is None:
            if hasattr(self.record_class, "application_name"):
                # Todo: Maybe make it support application_name without pipeline_id?
                assert hasattr(self.record_class, "pipeline_id"), self.record_class
                tmpl = self._insert_select_max_tmpl + self._where_application_name_tmpl
            else:
                tmpl = self._insert_select_max_tmpl
            self._insert_select_max = self._prepare_insert(
                tmpl=tmpl,
                record_class=self.record_class,
                field_names=list(self.field_names),
            )
        return self._insert_select_max

    @abstractmethod
    def _prepare_insert(
        self, tmpl, record_class, field_names, placeholder_for_id=False
    ):
        """
        Compile SQL statement with placeholders for bind parameters.
        """

    _insert_select_max_tmpl = (
        "INSERT INTO {tablename} ({notification_id}, {columns}) "
        "SELECT COALESCE(MAX({tablename}.{notification_id}), 0) + 1, {placeholders} "
        "FROM "
        "{tablename}"
    )

    @property
    @abstractmethod
    def _where_application_name_tmpl(self) -> str:
        pass

    @property
    def insert_values(self):
        """
        SQL statement that inserts records without ID.
        """
        if self._insert_values is None:
            self._insert_values = self._prepare_insert(
                tmpl=self._insert_values_tmpl,
                placeholder_for_id=True,
                record_class=self.record_class,
                field_names=self.field_names,
            )
        return self._insert_values

    @property
    def insert_tracking_record(self):
        """
        SQL statement that inserts tracking records.
        """
        if self._insert_tracking_record is None:
            self._insert_tracking_record = self._prepare_insert(
                tmpl=self._insert_values_tmpl,
                placeholder_for_id=True,
                record_class=self.tracking_record_class,
                field_names=self.tracking_record_field_names,
            )
        return self._insert_tracking_record

    _insert_values_tmpl = (
        "INSERT INTO {tablename} ({columns}) " "VALUES ({placeholders});"
    )

    @abstractmethod
    def get_record_table_name(self, record_class):
        """
        Returns table name - used in raw queries.

        :rtype: str
        """


class AbstractEventStore(ABC, Generic[TEvent]):
    """
    Abstract base class for event stores. Defines the methods
    expected of an event store by other classes in the library.
    """

    @abstractmethod
    def store(self, domain_event_or_events: OneOrManyEvents) -> None:
        """
        Put domain event in event store for later retrieval.
        """

    @abstractmethod
    def get_domain_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        is_ascending: bool = True,
        page_size: Optional[int] = None,
    ) -> Iterable[TEvent]:
        """
        Deprecated. Please use iter_domain_events() instead.

        Returns domain events for given entity ID.
        """

    @abstractmethod
    def iter_domain_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        is_ascending: bool = True,
        page_size: Optional[int] = None,
    ) -> Iterable[TEvent]:
        """
        Returns domain events for given entity ID.
        """

    @abstractmethod
    def get_domain_event(self, originator_id: UUID, position: int) -> TEvent:
        """
        Returns a single domain event.
        """

    @abstractmethod
    def get_most_recent_event(
        self, originator_id: UUID, lt: Optional[int] = None, lte: Optional[int] = None
    ) -> Optional[TEvent]:
        """
        Returns most recent domain event for given entity ID.
        """

    @abstractmethod
    def all_domain_events(self) -> Iterable[TEvent]:
        """
        Returns all domain events in the event store.
        """


class AbstractEventPlayer(Generic[TEntity, TEvent]):
    @property
    @abstractmethod
    def event_store(self) -> AbstractEventStore:
        """
        Returns event store object used by this repository.
        """

    @abstractmethod
    def get_and_project_events(
        self,
        entity_id: UUID,
        gt: Optional[int] = None,
        gte: Optional[int] = None,
        lt: Optional[int] = None,
        lte: Optional[int] = None,
        limit: Optional[int] = None,
        initial_state: Optional[TEntity] = None,
        query_descending: bool = False,
    ) -> Optional[TEntity]:
        pass


class AbstractSnapshop(ActualOccasion):
    @property
    @abstractmethod
    def topic(self) -> str:
        """
        Path to the class of the snapshotted entity.
        """

    @property
    @abstractmethod
    def state(self) -> str:
        """
        State of the snapshotted entity.
        """

    @property
    @abstractmethod
    def originator_id(self) -> UUID:
        """
        ID of the snapshotted entity.
        """

    @property
    @abstractmethod
    def originator_version(self) -> int:
        """
        Version of the last event applied to the entity.
        """


class AbstractEntityRepository(AbstractEventPlayer[TEntity, TEvent]):
    @abstractmethod
    def __getitem__(self, entity_id: UUID) -> TEntity:
        """
        Returns entity for given ID.

        Raises ``RepositoryKeyError`` when entity ID not found.
        """

    @abstractmethod
    def __contains__(self, entity_id: UUID) -> bool:
        """
        Returns True or False, according to whether or not entity exists.
        """

    @abstractmethod
    def get_entity(
        self, entity_id: UUID, at: Optional[int] = None
    ) -> Optional[TEntity]:
        """
        Returns entity for given ID.

        Returns None when entity ID not found.
        """

    @abstractmethod
    def take_snapshot(
        self, entity_id: UUID, lt: Optional[int] = None, lte: Optional[int] = None
    ) -> Optional[AbstractSnapshop]:
        """
        Takes snapshot of entity state, using stored events.
        """
