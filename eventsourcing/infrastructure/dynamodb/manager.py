from typing import (
    Any,
    Iterable,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
)
from uuid import UUID

from pynamodb.exceptions import DeleteError, PutError
from pynamodb.models import Model

from eventsourcing.exceptions import ProgrammingError
from eventsourcing.infrastructure.base import (
    RecordManagerWithNotifications,
    TrackingKwargs,
)

TPynamoDbModel = TypeVar("TPynamoDbModel", bound=Model)


class DynamoDbRecordManager(RecordManagerWithNotifications):
    """
    Record Manager for DynamoDB.
    """

    # TODO?: needed for batch save of many aggregates.
    # This framework saves the events in a ProcessEvent.
    def write_records(
            self,
            records: Iterable[Any],
            tracking_kwargs: Optional[TrackingKwargs] = None,
            orm_objs_pending_save: Optional[Sequence[Any]] = None,
            orm_objs_pending_delete: Optional[Sequence[Any]] = None,
    ) -> None:
        return

    def record_items(self, sequenced_items: Iterable[NamedTuple]) -> None:
        if not isinstance(sequenced_items, list):
            sequenced_items = list(sequenced_items)

        if len(sequenced_items) > 1:
            with self.record_class.batch_write() as batch:  # noqa
                for item in sequenced_items:
                    assert isinstance(item, self.sequenced_item_class), (
                        type(item),
                        self.sequenced_item_class,
                    )
                    record: Model = self.to_record(item)  # noqa
                    hash_key_name = record._hash_key_attribute().attr_name  # noqa
                    range_key_name = record._range_key_attribute().attr_name  # noqa
                    try:
                        self.get_record(
                            getattr(item, hash_key_name),
                            getattr(item, range_key_name),
                        )
                    except IndexError:
                        batch.save(record)
                    else:
                        self.raise_sequenced_item_conflict()

        elif len(sequenced_items) == 1:
            record: Model = self.to_record(sequenced_items[0])  # noqa
            range_key_attr = record._range_key_attribute()  # noqa
            range_key_name = range_key_attr.attr_name
            try:
                record.save(range_key_attr != getattr(record, range_key_name))  # noqa
            except PutError:
                self.raise_sequenced_item_conflict()

    def get_record(self, sequence_id: UUID, position: int) -> Any:
        model: Model = self.record_class  # noqa
        range_key_attr = model._range_key_attribute()  # noqa
        range_key_name = range_key_attr.attr_name
        range_field = getattr(model, range_key_name)
        kwargs = {'range_key_condition': range_field == position}
        query = model.query(sequence_id, **kwargs)
        try:
            record = list(query)[0]
        except IndexError:
            self.raise_index_error(position)
        else:
            return record

    def _compute_range_key_range(
        self,
        gt: Optional[int],
        gte: Optional[int],
        lt: Optional[int],
        lte: Optional[int],
    ) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        """
        Compute start/end indices and op for DynamoDB range key condition.

        The op in the returned tuple is None for true BETWEEN ranges.

        Examples:
            input: gt=None, gte=0, lt=3, lte=None
            output: (0, 2, None)  <-- this is a BETWEEN case

            input: gt=1, gte=None, lt=None, lte=None
            output: (2, None, '>')

            input: gt=None, gte=None, lt=None, lte=4
            output: (None, 4, '<=')

            input: gt=None, gte=None, lt=None, lte=None
            output: (None, None, None)

        :param gt: get items after this position
        :param gte: get items at or after this position
        :param lt: get items before this position
        :param lte: get items before or at this position
        :return: (start_index, end_index, op), where op is '>', '>=', '<', '<=', None
        :rtype: tuple
        """
        range_start = None
        range_end = None
        has_start = (gt is not None or gte is not None)
        has_end = (lt is not None or lte is not None)
        is_between = has_start and has_end

        # Compute start/end indices for DynamoDB BETWEEN key condition expression.
        if is_between:
            record_meta = self.record_class.Meta

            # Normalize indices to same type as delta for delta arithmetic
            range_type = getattr(record_meta, 'range_type', int)
            gt = range_type(gt) if gt is not None else None
            gte = range_type(gte) if gte is not None else None
            lt = range_type(lt) if lt is not None else None
            lte = range_type(lte) if lte is not None else None

            delta = range_type(getattr(record_meta, 'range_delta', 1))

            # Compute range key start index
            if gte is not None and gt is None:
                range_start = gte
            elif gt is not None and gte is None:
                range_start = gt + delta
            elif gt is not None and gte is not None:
                range_start = max(gt + delta, gte)

            # Compute range key end index
            if lte is not None and lt is None:
                range_end = lte
            elif lt is not None and lte is None:
                range_end = lt - delta
            elif lt is not None and lte is not None:
                range_end = min(lt - delta, lte)

            return range_start, range_end, None

        # Build condition operator
        op = None
        if gte is not None and gt is None:
            range_start = gte
            op = '>='
        elif gt is not None and gte is None:
            range_start = gt
            op = '>'
        elif lte is not None and lt is None:
            range_end = lte
            op = '<='
        elif lt is not None and lte is None:
            range_end = lt
            op = '<'

        return range_start, range_end, op

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
        assert limit is None or limit >= 1, limit
        assert not (gte and gt)
        assert not (lte and lt)

        model: Model = self.record_class  # noqa
        range_key_attr = model._range_key_attribute()  # noqa
        range_key_name = range_key_attr.attr_name
        range_field = getattr(model, range_key_name)
        kwargs = {}
        range_start, range_end, op = self._compute_range_key_range(gt, gte, lt, lte)
        if range_start is not None and range_end is not None:
            if range_start > range_end:
                return []
            kwargs = {
                'range_key_condition': range_field.between(range_start, range_end),
            }
        elif range_start is not None:
            if op == '>':
                kwargs = {'range_key_condition': range_field > range_start}
            elif op == '>=':
                kwargs = {'range_key_condition': range_field >= range_start}
        elif range_end is not None:
            if op == '<':
                kwargs = {'range_key_condition': range_field < range_end}
            elif op == '<=':
                kwargs = {'range_key_condition': range_field <= range_end}

        if limit is not None:
            kwargs.update({'limit': limit})

        kwargs.update({'scan_index_forward': query_ascending})
        query = model.query(sequence_id, **kwargs)
        items = list(query)

        # Reverse if necessary.
        if results_ascending != query_ascending:
            items.reverse()

        return items

    def all_sequence_ids(self) -> Iterable[UUID]:
        model: Model = self.record_class  # noqa
        query = model.scan()
        ids = {getattr(record, self.field_names.sequence_id) for record in query}
        for id_ in ids:
            yield id_

    def delete_record(self, record: Model) -> None:
        assert isinstance(record, self.record_class), type(record)
        range_key_attr = record._range_key_attribute()  # noqa
        range_key_name = range_key_attr.attr_name
        try:
            record.delete(range_key_attr == getattr(record, range_key_name))  # noqa
        except DeleteError as e:
            raise ProgrammingError(e)

    def get_max_notification_id(self) -> None:
        """
        Needed when subclassing RecordManagerWithNotifications
        """
        return

    def get_notification_records(
            self,
            start: Optional[int] = None,
            stop: Optional[int] = None,
            *args: Any,
            **kwargs: Any
    ) -> Iterable:
        """
        Needed when subclassing RecordManagerWithNotifications
        """
        return ()
