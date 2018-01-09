# coding=utf-8
from abc import ABCMeta, abstractmethod

import six

from eventsourcing.exceptions import ConcurrencyError, SequencedItemConflict
from eventsourcing.infrastructure.base import AbstractRecordManager
from eventsourcing.infrastructure.iterators import SequencedItemIterator
from eventsourcing.infrastructure.sequenceditemmapper import AbstractSequencedItemMapper


class AbstractEventStore(six.with_metaclass(ABCMeta)):
    """
    Abstract base class for event stores. Defines the methods
    expected of an event store by other classes in the library.
    """
    @abstractmethod
    def append(self, domain_event_or_events):
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
    def get_domain_event(self, originator_id, eq):
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
        assert isinstance(record_manager, AbstractRecordManager), record_manager
        assert isinstance(sequenced_item_mapper, AbstractSequencedItemMapper), sequenced_item_mapper
        self.record_manager = record_manager
        self.sequenced_item_mapper = sequenced_item_mapper

    def append(self, domain_event_or_events):
        """
        Appends given domain event, or list of domain events, to their sequence.

        :param domain_event_or_events: domain event, or list of domain events
        """

        # Convert the domain event(s) to sequenced item(s).
        if isinstance(domain_event_or_events, (list, tuple)):
            sequenced_item_or_items = [self.to_sequenced_item(e) for e in domain_event_or_events]
        else:
            sequenced_item_or_items = self.to_sequenced_item(domain_event_or_events)

        # Append to the sequenced item(s) to the sequence.
        try:
            self.record_manager.append(sequenced_item_or_items)
        except SequencedItemConflict as e:
            raise ConcurrencyError(e)

    def to_sequenced_item(self, domain_event):
        """
        Maps domain event to sequenced item namedtuple.

        :param domain_event: application-level object
        :return: namedtuple: sequence item namedtuple
        """
        return self.sequenced_item_mapper.to_sequenced_item(domain_event)

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
        domain_events = six.moves.map(self.sequenced_item_mapper.from_sequenced_item, sequenced_items)
        domain_events = list(domain_events)
        return domain_events

    def get_domain_event(self, originator_id, eq):
        """
        Gets a domain event from the sequence identified by `originator_id`
        at position `eq`.

        :param originator_id: ID of a sequence of events
        :param eq: get item at this position
        :return: domain event
        """
        sequenced_item = self.record_manager.get_item(
            sequence_id=originator_id,
            eq=eq,
        )
        domain_event = self.sequenced_item_mapper.from_sequenced_item(sequenced_item)
        return domain_event

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
        Gets all domain events in the event store.

        :return: map object, yielding a sequence of domain events
        """
        all_items = self.record_manager.all_items()
        return map(self.sequenced_item_mapper.from_sequenced_item, all_items)
