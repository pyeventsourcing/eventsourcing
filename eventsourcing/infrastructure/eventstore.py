# coding=utf-8
from abc import ABCMeta, abstractmethod

import six

from eventsourcing.exceptions import ConcurrencyError, SequencedItemError
from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.iterators import SequencedItemIterator
from eventsourcing.infrastructure.sequenceditemmapper import AbstractSequencedItemMapper


class AbstractEventStore(six.with_metaclass(ABCMeta)):
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
    iterator_class = SequencedItemIterator

    def __init__(self, active_record_strategy, sequenced_item_mapper=None):
        assert isinstance(active_record_strategy, AbstractActiveRecordStrategy), active_record_strategy
        assert isinstance(sequenced_item_mapper, AbstractSequencedItemMapper), sequenced_item_mapper
        self.active_record_strategy = active_record_strategy
        self.sequenced_item_mapper = sequenced_item_mapper

    def append(self, domain_event_or_events):
        # Convert the domain event(s) to sequenced item(s).
        if isinstance(domain_event_or_events, (list, tuple)):
            sequenced_item_or_items = [self.to_sequenced_item(e) for e in domain_event_or_events]
        else:
            sequenced_item_or_items = self.to_sequenced_item(domain_event_or_events)

        # Append to the sequenced item(s) to the sequence.
        try:
            self.active_record_strategy.append(sequenced_item_or_items)
        except SequencedItemError as e:
            raise ConcurrencyError(e)

    def to_sequenced_item(self, domain_event):
        return self.sequenced_item_mapper.to_sequenced_item(domain_event)

    def get_domain_events(self, originator_id, gt=None, gte=None, lt=None, lte=None, limit=None, is_ascending=True,
                          page_size=None):
        # Get all the sequenced items for the entity.
        if page_size:
            sequenced_items = self.iterator_class(
                active_record_strategy=self.active_record_strategy,
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
            sequenced_items = self.active_record_strategy.get_items(
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
        sequenced_item = self.active_record_strategy.get_item(
            sequence_id=originator_id,
            eq=eq,
        )
        domain_event = self.sequenced_item_mapper.from_sequenced_item(sequenced_item)
        return domain_event

    def get_most_recent_event(self, originator_id, lt=None, lte=None):
        events = self.get_domain_events(originator_id=originator_id, lt=lt, lte=lte, limit=1, is_ascending=False)
        events = list(events)
        try:
            return events[0]
        except IndexError:
            pass

    def all_domain_events(self):
        all_items = self.active_record_strategy.all_items()
        return map(self.sequenced_item_mapper.from_sequenced_item, all_items)
