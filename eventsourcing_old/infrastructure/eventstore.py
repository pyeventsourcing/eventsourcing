from typing import Iterable, NamedTuple, Optional
from uuid import UUID

from eventsourcing.exceptions import ConcurrencyError, RecordConflictError
from eventsourcing.infrastructure.base import AbstractEventStore, TRecordManager
from eventsourcing.infrastructure.iterators import SequencedItemIterator
from eventsourcing.whitehead import TEvent

# Todo: Unify iterators in EventStore and in NotificationLog,
#  by pushing behaviour down to record manager?


class EventStore(AbstractEventStore[TEvent, TRecordManager]):
    """
    Event store appends domain events to stored sequences. It uses
    a record manager to map named tuples to database
    records, and it uses a sequenced item mapper to map named
    tuples to application-level objects.
    """

    iterator_class = SequencedItemIterator

    def store_events(self, events: Iterable[TEvent]) -> None:
        """
        Appends given domain event, or list of domain events, to their sequence.

        :param events: domain event, or list of domain events
        """

        # Convert to sequenced item.
        sequenced_items = self.items_from_events(events)

        # Append to the sequenced item(s) to the sequence.
        try:
            self.record_manager.record_items(sequenced_items)
        except RecordConflictError as e:
            raise ConcurrencyError(e)

    def items_from_events(self, events: Iterable[TEvent]) -> Iterable[NamedTuple]:
        """
        Maps domain event to sequenced item namedtuple.

        An iterable of events.
        """
        # Convert the domain event(s) to sequenced item(s).
        return map(self.event_mapper.item_from_event, events)

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
        if self.record_manager.can_limit_get_records and page_size:
            sequenced_items: Iterable = self.iterator_class(
                record_manager=self.record_manager,
                sequence_id=originator_id,
                page_size=page_size,
                gt=gt,
                gte=gte,
                lt=lt,
                lte=lte,
                limit=limit,
                is_ascending=is_ascending,
            )
        else:
            sequenced_items = self.record_manager.get_items(
                sequence_id=originator_id,
                gt=gt,
                gte=gte,
                lt=lt,
                lte=lte,
                limit=limit,
                query_ascending=is_ascending,
                results_ascending=is_ascending,
            )

        # Deserialize to domain events.
        return map(self.event_mapper.event_from_item, sequenced_items)

    def get_event(self, originator_id: UUID, position: int) -> TEvent:
        """
        Gets a domain event from the sequence identified by `originator_id`
        at position `eq`.

        :param originator_id: ID of a sequence of events
        :param position: get item at this position
        :return: domain event
        """
        sequenced_item = self.record_manager.get_item(
            sequence_id=originator_id, position=position
        )
        return self.event_mapper.event_from_item(sequenced_item)

    def get_most_recent_event(
        self, originator_id: UUID, lt: Optional[int] = None, lte: Optional[int] = None
    ) -> Optional[TEvent]:
        """
        Gets a domain event from the sequence identified by `originator_id`
        at the highest position.

        :param originator_id: ID of a sequence of events
        :param lt: get highest before this position
        :param lte: get highest at or before this position
        :return: domain event
        """
        events = self.list_events(
            originator_id=originator_id, lt=lt, lte=lte, limit=1, is_ascending=False
        )
        len_events = len(events)
        if len_events == 1:
            return events[0]
        elif len_events == 0:
            return None
        else:
            raise AssertionError("Too many events: %s" % len_events)

    def all_events(self) -> Iterable[TEvent]:
        """
        Yields all domain events in the event store.

        This method iterates over the sequence IDs,
        and returns all the events for each sequence
        effectively concatenated together.

        Use a notification log to propagate events from
        an application as a stable append-only sequence.
        """
        for originator_id in self.record_manager.all_sequence_ids():
            for domain_event in self.iter_events(
                originator_id=originator_id, page_size=100
            ):
                yield domain_event
