# coding=utf-8
from abc import ABCMeta, abstractmethod

import six

from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.iterators import SequencedItemIterator
from eventsourcing.infrastructure.transcoding import AbstractSequencedItemMapper


class AbstractEventStore(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def append(self, domain_event):
        """
        Put domain event in event store for later retrieval.
        """

    @abstractmethod
    def get_domain_events(self, entity_id, gt=None, gte=None, lt=None, lte=None, limit=None, is_ascending=True,
                          page_size=None):
        """
        Returns domain events for given entity ID.
        """

    def get_most_recent_event(self, entity_id, lt=None, lte=None):
        """
        Returns most recent domain event for given entity ID.
        """


class EventStore(AbstractEventStore):
    iterator_class = SequencedItemIterator

    def __init__(self, active_record_strategy, sequenced_item_mapper=None):
        assert isinstance(active_record_strategy, AbstractActiveRecordStrategy), active_record_strategy
        assert isinstance(sequenced_item_mapper, AbstractSequencedItemMapper), sequenced_item_mapper
        self.active_record_strategy = active_record_strategy
        self.sequenced_item_mapper = sequenced_item_mapper

    def append(self, domain_event):
        # Serialize the domain event as a sequenced item.
        sequenced_item = self.sequenced_item_mapper.to_sequenced_item(domain_event)

        # Append to the item to the sequence.
        self.active_record_strategy.append_item(sequenced_item)

    def get_domain_events(self, entity_id, gt=None, gte=None, lt=None, lte=None, limit=None, is_ascending=True,
                          page_size=None):
        # Get all the sequenced items for the entity.
        if page_size:
            sequenced_items = self.iterator_class(
                active_record_strategy=self.active_record_strategy,
                sequence_id=entity_id,
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
                sequence_id=entity_id,
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

    def get_most_recent_event(self, entity_id, lt=None, lte=None):
        events = self.get_domain_events(entity_id=entity_id, lt=lt, lte=lte, limit=1, is_ascending=False)
        events = list(events)
        try:
            return events[0]
        except IndexError:
            pass


class SequencedItemRepository(six.with_metaclass(ABCMeta)):
    def __init__(self, active_record_strategy):
        assert isinstance(active_record_strategy, AbstractActiveRecordStrategy)
        self.active_record_strategy = active_record_strategy

    def get_items(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                  query_ascending=True, results_ascending=True):
        """Returns items in sequence."""
        return self.active_record_strategy.get_items(
            sequence_id,
            gt=gt,
            gte=gte,
            lt=gte,
            lte=lte,
            limit=limit,
            query_ascending=query_ascending,
            results_ascending=results_ascending,
        )

    def append_item(self, item):
        """Appends item to sequence."""
        self.active_record_strategy.append_item(item)
