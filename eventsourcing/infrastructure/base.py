from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from uuid import UUID

from eventsourcing.exceptions import OperationalError, RecordConflictError
from eventsourcing.infrastructure.sequenceditem import (
    SequencedItem,
    SequencedItemFieldNames,
)
from eventsourcing.infrastructure.sequenceditemmapper import AbstractSequencedItemMapper
from eventsourcing.whitehead import TEvent

DEFAULT_PIPELINE_ID = 0

TrackingKwargs = Dict[str, Union[str, int]]


class AbstractRecordManager(ABC):
    has_integrated_snapshots = False
    can_limit_get_records = True
    can_lt_lte_get_records = True
    can_list_sequence_ids = True
    can_delete_records = True

    def __init__(self, **kwargs: Any):
        """
        Initialises record manager.
        """

    @property
    @abstractmethod
    def record_class(self) -> Any:
        """
        Returns record class to be used by the record manager.
        """

    @abstractmethod
    def record_items(self, sequenced_items: Iterable[NamedTuple]) -> None:
        """
        Writes sequenced items into the datastore.
        """

    def record_item(self, sequenced_item: NamedTuple) -> None:
        """
        Writes sequenced item into the datastore.
        """
        self.record_items([sequenced_item])

    @abstractmethod
    def get_item(self, sequence_id: UUID, position: int) -> NamedTuple:
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
    ) -> Iterator[NamedTuple]:
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
    def all_sequence_ids(self) -> Iterable[UUID]:
        """
        Returns all sequence IDs.
        """

    @abstractmethod
    def delete_record(self, record: Any) -> None:
        """
        Removes permanently given record from the table.
        """


TRecordManager = TypeVar("TRecordManager", bound=AbstractRecordManager)


class BaseRecordManager(AbstractRecordManager):
    def __init__(
        self,
        record_class: type,
        sequenced_item_class: Type[NamedTuple] = SequencedItem,  # type: ignore
        contiguous_record_ids: bool = False,
        application_name: str = "",
        pipeline_id: int = DEFAULT_PIPELINE_ID,
        **kwargs: Any
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

        self.contiguous_record_ids = bool(
            contiguous_record_ids and self.notification_id_name
        )
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
        self._pipeline_id = pipeline_id

    @property
    def record_class(self) -> type:
        return self._record_class

    @property
    def pipeline_id(self) -> int:
        return self._pipeline_id

    @pipeline_id.setter
    def pipeline_id(self, pipeline_id: int) -> None:
        self._pipeline_id = pipeline_id

    def clone(
        self, application_name: str, pipeline_id: int, **kwargs: Any
    ) -> "BaseRecordManager":
        return type(self)(
            record_class=self.record_class,
            contiguous_record_ids=self.contiguous_record_ids,
            sequenced_item_class=self.sequenced_item_class,
            application_name=application_name,
            pipeline_id=pipeline_id,
            **kwargs
        )

    def get_item(self, sequence_id: UUID, position: int) -> NamedTuple:
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
    ) -> Iterator[NamedTuple]:
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

    def list_items(self, *args: Any, **kwargs: Any) -> List[NamedTuple]:
        """
        Returns list of sequenced items.
        """
        return list(self.get_items(*args, **kwargs))

    def to_record(self, sequenced_item: NamedTuple) -> object:
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

    def from_record(self, record: object) -> NamedTuple:
        """
        Constructs and returns a sequenced item object, from given ORM object.
        """
        kwargs = self.get_field_kwargs(record)
        return self.sequenced_item_class(**kwargs)

    def list_sequence_ids(self) -> List[UUID]:
        return list(self.all_sequence_ids())

    def get_field_kwargs(self, item: object) -> Dict[str, Any]:
        return {name: getattr(item, name) for name in self.field_names}

    def raise_sequenced_item_conflict(self, exp=None) -> None:
        msg = "Position already taken in sequence"
        raise RecordConflictError(exp or msg)

    def raise_index_error(self, position: int) -> None:
        raise IndexError("Sequence index out of range: {}".format(position))

    def raise_record_integrity_error(self, e: Exception) -> None:
        raise RecordConflictError(e)

    def raise_operational_error(self, e: Exception) -> None:
        raise OperationalError(e)


class RecordManagerWithNotifications(BaseRecordManager):
    @abstractmethod
    def get_max_notification_id(self) -> int:
        """Return maximum notification ID in pipeline."""

    @abstractmethod
    def get_notification_records(
        self,
        start: Optional[int] = None,
        stop: Optional[int] = None,
        *args: Any,
        **kwargs: Any
    ) -> Iterable:
        """
        Returns records sequenced by notification ID, from
        application, for pipeline, in given range.

        Args 'start' and 'stop' are positions in a zero-based
        integer sequence.
        """

    def get_notifications(
        self,
        start: Optional[int] = None,
        stop: Optional[int] = None,
        *args: Any,
        **kwargs: Any
    ) -> Iterable:
        for record in self.get_notification_records(
            start=start, stop=stop, *args, **kwargs
        ):
            yield self.create_notification_from_record(record)

    def create_notification_from_record(self, record):
        notification = {"id": getattr(record, self.notification_id_name)}
        for field_name in self.field_names:
            notification[field_name] = getattr(record, field_name)
        if hasattr(record, "causal_dependencies"):
            notification["causal_dependencies"] = record.causal_dependencies
        return notification


class RecordManagerWithTracking(RecordManagerWithNotifications):
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

    def __init__(
        self, tracking_record_class: Optional[type] = None, *args: Any, **kwargs: Any
    ) -> None:
        super(RecordManagerWithTracking, self).__init__(*args, **kwargs)
        # assert tracking_record_class is not None
        self.tracking_record_class = tracking_record_class

    def clone(
        self, application_name: str, pipeline_id: int, **kwargs: Any
    ) -> "BaseRecordManager":
        return super().clone(
            application_name=application_name,
            pipeline_id=pipeline_id,
            tracking_record_class=self.tracking_record_class,
            **kwargs
        )

    @abstractmethod
    def write_records(
        self,
        records: Iterable[Any],
        tracking_kwargs: Optional[TrackingKwargs] = None,
        orm_objs_pending_save: Optional[Sequence[Any]] = None,
        orm_objs_pending_delete: Optional[Sequence[Any]] = None,
    ) -> None:
        """
        Writes tracking, event and notification records for a process event.
        :param orm_objs_pending_delete:
        :param orm_objs_pending_save:
        """

    def to_records(self, sequenced_items: Iterable[NamedTuple]) -> Iterable[Any]:
        return map(self.to_record, sequenced_items)

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

    def get_pipeline_and_notification_id(
        self, sequence_id: UUID, position: int
    ) -> Tuple:
        """
        Returns pipeline ID and notification ID for
        event at given position in given sequence.
        """
        # Todo: Optimise query by selecting only two columns,
        #  pipeline_id and id (notification ID)?
        record = self.get_record(sequence_id, position)
        notification_id = getattr(record, self.notification_id_name)
        return record.pipeline_id, notification_id


class SQLRecordManager(RecordManagerWithTracking):
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

    def __init__(self, *args: Any, **kwargs: Any):
        super(SQLRecordManager, self).__init__(*args, **kwargs)
        self._insert_select_max = None
        self._insert_values = None
        self._insert_tracking_record = None

    def record_items(self, sequenced_items: Iterable[NamedTuple]) -> None:
        # Convert sequenced item(s) to database record(s).
        records = self.to_records(sequenced_items)

        # Write records.
        self.write_records(records)

    @property
    def insert_select_max(self) -> Any:
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

    def _prepare_insert(
        self,
        tmpl: str,
        record_class: type,
        field_names: List[str],
        placeholder_for_id: bool = False,
    ) -> Any:
        """
        With transaction isolation level of "read committed" this should
        generate records with a contiguous sequence of integer IDs, using
        an indexed ID column, the database-side SQL max function, the
        insert-select-from form, and optimistic concurrency control.
        """
        if (
            hasattr(record_class, "application_name")
            and "application_name" not in field_names
        ):
            field_names.append("application_name")
        if hasattr(record_class, "pipeline_id") and "pipeline_id" not in field_names:
            field_names.append("pipeline_id")
        if (
            hasattr(record_class, "causal_dependencies")
            and "causal_dependencies" not in field_names
        ):
            field_names.append("causal_dependencies")
        if self.notification_id_name:
            if placeholder_for_id:
                if self.notification_id_name not in field_names:
                    field_names.append(self.notification_id_name)

        statement = tmpl.format(
            tablename=self.get_record_table_name(record_class),
            columns=", ".join(field_names),
            placeholders=", ".join([self.make_placeholder(f) for f in field_names]),
            notification_id=self.notification_id_name,
        )
        return statement

    @abstractmethod
    def make_placeholder(self, field_name: str) -> str:
        """
        Returns "placeholder" string for late binding of values to query.

        Depends on record manager's adapted database system or adapted ORM.
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
        """
        Returns template string for "WHERE" clause of SQL statement.
        """

    @property
    def insert_values(self) -> Any:
        """
        SQL statement that inserts records without ID.
        """
        if self._insert_values is None:
            self._insert_values = self._prepare_insert(
                tmpl=self._insert_values_tmpl,
                placeholder_for_id=True,
                record_class=self.record_class,
                field_names=list(self.field_names),
            )
        return self._insert_values

    @property
    def insert_tracking_record(self) -> Any:
        """
        SQL statement that inserts tracking records.
        """
        if self._insert_tracking_record is None:
            assert self.tracking_record_class is not None
            self._insert_tracking_record = self._prepare_insert(
                tmpl=self._insert_values_tmpl,
                placeholder_for_id=True,
                record_class=self.tracking_record_class,
                field_names=self.tracking_record_field_names,
            )
        return self._insert_tracking_record

    _insert_values_tmpl = (
        "INSERT INTO {tablename} ({columns}) " "VALUES ({placeholders})"
    )

    @abstractmethod
    def get_record_table_name(self, record_class: type) -> str:
        """
        Returns table name - used in raw queries.

        :rtype: str
        """


class AbstractEventStore(ABC, Generic[TEvent, TRecordManager]):
    """
    Abstract base class for event stores. Defines the methods
    expected of an event store by other classes in the library.
    """

    def __init__(
        self, record_manager: TRecordManager, event_mapper: AbstractSequencedItemMapper,
    ):
        """
        Initialises event store object.


        :param record_manager: record manager
        :param event_mapper: sequenced item mapper
        """
        self.record_manager = record_manager
        self.event_mapper = event_mapper

    @abstractmethod
    def store_events(self, events: Iterable[TEvent]) -> None:
        """
        Put domain event in event store for later retrieval.
        """

    @abstractmethod
    def iter_events(
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
        Returns iterable of domain events for given entity ID.
        """

    def list_events(self, *args: Any, **kwargs: Any) -> List[TEvent]:
        """
        Returns list of domain events for given entity ID.
        """
        return list(self.iter_events(*args, **kwargs))

    @abstractmethod
    def get_event(self, originator_id: UUID, position: int) -> TEvent:
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
    def all_events(self) -> Iterable[TEvent]:
        """
        Returns all domain events in the event store.

        This works by iterating over all sequences,
        so doesn't return events in order. Use a
        Notification Log to project application state.
        """

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
        Deprecated. Please use iter_events() instead.

        Gets domain events from the sequence identified by `originator_id`.

        :param originator_id: ID of a sequence of events
        :param gt: get items after this position
        :param gte: get items at or after this position
        :param lt: get items before this position
        :param lte: get items before or at this position
        :param limit: get limited number of items
        :param is_ascending: get items from lowest position
        :param page_size: restrict and repeat database query
        :return: list of domain events
        """
        return self.iter_events(
            originator_id=originator_id,
            gt=gt,
            gte=gte,
            lt=lt,
            lte=lte,
            limit=limit,
            is_ascending=is_ascending,
            page_size=page_size,
        )

    @abstractmethod
    def items_from_events(self, events: Iterable[TEvent]) -> Iterable[NamedTuple]:
        """
        Maps domain event to sequenced item namedtuple.

        :param events: An iterable of events.
        """
