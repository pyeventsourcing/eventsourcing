# coding=utf-8
from abc import ABC, abstractmethod

from eventsourcing.exceptions import ConcurrencyError, RecordConflictError
from eventsourcing.infrastructure.base import AbstractSequencedItemRecordManager
from eventsourcing.infrastructure.iterators import SequencedItemIterator
from eventsourcing.infrastructure.sequenceditemmapper import AbstractSequencedItemMapper


class AbstractEventStore(ABC):
    """
    Abstract base class for event stores. Defines the methods
    expected of an event store by other classes in the library.
    """

    @abstractmethod
    def store(self, domain_event_or_events):
        """
        Put domain event in event store for later retrieval.
        """

    @abstractmethod
    def get_domain_events(self, originator_id, gt=None, gte=None, lt=None, lte=None, limit=None, is_ascending=True,
                          page_size=None):
        """
        Returns domain events for given entity ID.
        """

    @abstractmethod
    def get_domain_event(self, originator_id, position):
        """
        Returns a single domain event.
        """

    @abstractmethod
    def get_most_recent_event(self, originator_id, lt=None, lte=None):
        """
        Returns most recent domain event for given entity ID.
        """

    @abstractmethod
    def all_domain_events(self):
        """
        Returns all domain events in the event store.
        """


# Todo: Unify iterators in EventStore and in NotificationLog, by pushing behaviour down to record manager?

class EventStore(AbstractEventStore):
    """
    Event store appends domain events to stored sequences. It uses
    a record manager to map named tuples to database
    records, and it uses a sequenced item mapper to map named
    tuples to application-level objects.
    """
    iterator_class = SequencedItemIterator

    def __init__(self, record_manager, sequenced_item_mapper):
        """
        Initialises event store object.


        :param record_manager: record manager
        :param sequenced_item_mapper: sequenced item mapper
        """
        assert isinstance(record_manager, AbstractSequencedItemRecordManager), record_manager
        assert isinstance(sequenced_item_mapper, AbstractSequencedItemMapper), sequenced_item_mapper
        self.record_manager = record_manager
        self.mapper = sequenced_item_mapper

    def store(self, domain_event_or_events):
        """
        Appends given domain event, or list of domain events, to their sequence.

        :param domain_event_or_events: domain event, or list of domain events
        """

        # Convert to sequenced item.
        sequenced_item_or_items = self.item_from_event(domain_event_or_events)

        # Append to the sequenced item(s) to the sequence.
        try:
            self.record_manager.record_sequenced_items(sequenced_item_or_items)
        except RecordConflictError as e:
            raise ConcurrencyError(e)

    def item_from_event(self, domain_event_or_events):
        """
        Maps domain event to sequenced item namedtuple.

        :param domain_event_or_events: application-level object (or list)
        :return: namedtuple: sequence item namedtuple (or list)
        """
        # Convert the domain event(s) to sequenced item(s).
        if isinstance(domain_event_or_events, (list, tuple)):
            return [self.item_from_event(e) for e in domain_event_or_events]
        else:
            return self.mapper.item_from_event(domain_event_or_events)

    def get_domain_events(self, originator_id, gt=None, gte=None, lt=None, lte=None, limit=None, is_ascending=True,
                          page_size=None):
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
        if page_size:
            sequenced_items = self.iterator_class(
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
        domain_events = map(self.mapper.event_from_item, sequenced_items)
        return list(domain_events)

    def get_domain_event(self, originator_id, position):
        """
        Gets a domain event from the sequence identified by `originator_id`
        at position `eq`.

        :param originator_id: ID of a sequence of events
        :param position: get item at this position
        :return: domain event
        """

        sequenced_item = self.record_manager.get_item(
            sequence_id=originator_id,
            position=position,
        )
        return self.mapper.event_from_item(sequenced_item)

    def get_most_recent_event(self, originator_id, lt=None, lte=None):
        """
        Gets a domain event from the sequence identified by `originator_id`
        at the highest position.

        :param originator_id: ID of a sequence of events
        :param lt: get highest before this position
        :param lte: get highest at or before this position
        :return: domain event
        """
        events = self.get_domain_events(originator_id=originator_id, lt=lt, lte=lte, limit=1, is_ascending=False)
        events = list(events)
        try:
            return events[0]
        except IndexError:
            pass

    def all_domain_events(self):
        """
        Yields all domain events in the event store.
        """
        for originator_id in self.record_manager.all_sequence_ids():
            for domain_event in self.get_domain_events(originator_id=originator_id, page_size=100):
                yield domain_event
