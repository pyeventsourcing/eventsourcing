# coding=utf-8
from abc import ABCMeta, abstractmethod

import six

from eventsourcing.domain.model.events import OldDomainEvent, NewDomainEvent
from eventsourcing.exceptions import EntityVersionNotFound
from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy
from eventsourcing.infrastructure.iterators import SequencedItemIterator
from eventsourcing.infrastructure.transcoding import AbstractSequencedItemMapper, JSONStoredEventTranscoder, \
    SequencedItem, StoredEvent, StoredEventTranscoder


class AbstractEventStore(six.with_metaclass(ABCMeta)):
    @abstractmethod
    def append(self, domain_event):
        """
        Put domain event in event store for later retrieval.
        """

    @abstractmethod
    def get_domain_events(self, entity_id, after=None, until=None, limit=None, is_ascending=True, page_size=None):
        """Returns domain events for given stored entity ID."""

    def get_most_recent_event(self, entity_id, lt=None, lte=None):
        """Returns most recent domain event for given entity ID."""


class EventStore(AbstractEventStore):
    def __init__(self, stored_event_repo, transcoder=None):
        assert isinstance(stored_event_repo, AbstractStoredEventRepository), stored_event_repo
        if transcoder is None:
            transcoder = JSONStoredEventTranscoder()
        assert isinstance(transcoder, StoredEventTranscoder), transcoder
        self.stored_event_repo = stored_event_repo

        self.transcoder = transcoder

    def append(self, domain_event):
        assert isinstance(domain_event, OldDomainEvent), type(domain_event)
        # Serialize the domain event.
        stored_event = self.transcoder.serialize(domain_event)

        # Append the stored event to the stored event repo.
        self.stored_event_repo.append(
            new_stored_event=stored_event,
            new_version_number=domain_event.entity_version,
        )

    def get_domain_events(self, entity_id, after=None, until=None, limit=None, is_ascending=True,
                          page_size=None):
        # Get the events that have been stored for the entity.
        if page_size:
            stored_events = self.stored_event_repo.iterate_stored_events(
                stored_entity_id=entity_id,
                after=after,
                until=until,
                limit=limit,
                is_ascending=is_ascending,
                page_size=page_size
            )
        else:
            stored_events = self.stored_event_repo.get_stored_events(
                stored_entity_id=entity_id,
                after=after,
                until=until,
                limit=limit,
                query_ascending=is_ascending,
                results_ascending=is_ascending,
            )

        # Deserialize all the stored event objects into domain event objects.
        return six.moves.map(self.transcoder.deserialize, stored_events)

    def get_most_recent_event(self, stored_entity_id, until=None, include_until=False):
        """Returns last event for given stored entity ID.

        :rtype: OldDomainEvent, NoneType
        """
        stored_event = self.stored_event_repo.get_most_recent_event(stored_entity_id, until=until,
                                                                    include_until=include_until)
        return None if stored_event is None else self.transcoder.deserialize(stored_event)

    def get_entity_version(self, stored_entity_id, version):
        return self.stored_event_repo.get_entity_version(stored_entity_id=stored_entity_id, version_number=version)


class NewEventStore(AbstractEventStore):

    iterator_class = SequencedItemIterator

    def __init__(self, active_record_strategy, sequenced_item_mapper=None):
        assert isinstance(active_record_strategy, AbstractActiveRecordStrategy), active_record_strategy
        assert isinstance(sequenced_item_mapper, AbstractSequencedItemMapper), sequenced_item_mapper
        self.active_record_strategy = active_record_strategy
        self.sequenced_item_mapper = sequenced_item_mapper

    def append(self, domain_event):
        assert isinstance(domain_event, NewDomainEvent)
        # Serialize the domain event as a sequenced item.
        sequenced_item = self.sequenced_item_mapper.to_sequenced_item(domain_event)

        # Append to the item to the sequence.
        self.active_record_strategy.append_item(sequenced_item)

    def get_domain_events(self, entity_id, gt=None, gte=None, lt=None, lte=None, limit=None, is_ascending=True,
                          page_size=None):
        # Get all the sequenced items for the entity.
        if page_size:
            iterator = self.iterator_class(
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
            sequenced_items = list(iterator)
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
        return six.moves.map(self.sequenced_item_mapper.from_sequenced_item, sequenced_items)

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


class AbstractStoredEventRepository(six.with_metaclass(ABCMeta)):
    stored_event_class = StoredEvent
    sequenced_item_type = SequencedItem

    # Todo: Change stored_event_class to be a class attribute, rather than constructor argument.
    # - does that support the use case of substituting a customer stored event class? write a test first
    def __init__(self, always_check_expected_version=False, always_write_entity_version=False):
        """
        Abstract base class for a persistent collection of stored events.
        """
        self.always_check_expected_version = always_check_expected_version
        self.always_write_entity_version = always_write_entity_version or always_check_expected_version

    def append(self, new_stored_event, new_version_number=None, max_retries=3, artificial_failure_rate=0):
        """
        Saves given stored event in this repository.
        """
        # Check the new event is a stored event instance.
        assert isinstance(new_stored_event, self.stored_event_class), (new_stored_event, self.stored_event_class)

        # Validate the expected version.
        if self.always_check_expected_version:
            # noinspection PyTypeChecker
            self.validate_expected_version(new_stored_event, new_version_number)

        # Write the event.
        self.write_version_and_event(
            new_stored_event=new_stored_event,
            new_version_number=new_version_number,
            max_retries=max_retries,
            artificial_failure_rate=artificial_failure_rate,
        )

    def validate_expected_version(self, new_stored_event, new_version_number):
        """
        Checks the expected version exists and occurred before the new event.

        Raises a concurrency error if the expected version doesn't exist,
        or if the new event occurred before the expected version occurred.
        """
        assert isinstance(new_stored_event, self.stored_event_class)

        stored_entity_id = new_stored_event.entity_id
        expected_version_number = self.decide_expected_version_number(new_version_number)
        if expected_version_number is not None:
            assert isinstance(expected_version_number, six.integer_types)
            self.get_entity_version(
                stored_entity_id=stored_entity_id,
                version_number=expected_version_number
            )
            # else:
            #     if not time_from_uuid(new_stored_event.event_id) > time_from_uuid(entity_version.event_id):
            #         raise ConcurrencyError("New event ID '{}' occurs before last version event ID '{}' for
            # entity {}"
            #                                "".format(new_stored_event.event_id, entity_version.event_id,
            # entity_id))

    def decide_expected_version_number(self, new_version_number):
        return new_version_number - 1 if new_version_number else None

    @abstractmethod
    def get_entity_version(self, stored_entity_id, version_number):
        """
        Returns entity version object for given entity version ID.

        :rtype: EntityVersion

        """

    @abstractmethod
    def write_version_and_event(self, new_stored_event, new_entity_version=None, max_retries=3,
                                artificial_failure_rate=0):
        """
        Writes entity version and stored event into a database.
        """

    @abstractmethod
    def get_stored_events(self, stored_entity_id, after=None, until=None, limit=None, query_ascending=True,
                          results_ascending=True, include_after_when_ascending=False,
                          include_until_when_descending=False):
        """
        Returns all stored events for given entity ID in chronological order. Limit is max 10000.

        :rtype: list

        """

    # @abstractmethod
    def append_integer_sequenced_item(self, event):
        """
        Appends given integer sequenced item to this repository.
        """
        # Check the new event is a stored event instance.
        assert isinstance(event, self.stored_event_class), (event, self.stored_event_class)

    # @abstractmethod
    def get_integer_sequenced_items(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                                    query_ascending=True, results_ascending=True):
        """
        Returns all integer sequenced events for given sequence ID, in sequential order.

        :param gte:
        :param lte:
        :rtype: list

        """

    # @abstractmethod
    def append_time_sequenced_item(self, item):
        """
        Appends a time sequenced item to the sequence.
        """
        assert isinstance(item, self.sequenced_item_type), (item, self.sequenced_item_type)

    # @abstractmethod
    def get_time_sequenced_items(self, sequence_id, gt=None, gte=None, lt=None, lte=None, limit=None,
                                 query_ascending=True, results_ascending=True):
        """
        Returns all time sequenced items for given sequence ID, in sequential order.

        :param gte:
        :param lte:
        :rtype: list

        """

    def iterate_stored_events(self, stored_entity_id, after=None, until=None, limit=None, is_ascending=True,
                              page_size=None):
        """
        Returns all stored events for given entity ID by paging through the stored events.

        :rtype: list

        """
        return self.iterator_class(
            repo=self,
            stored_entity_id=stored_entity_id,
            page_size=min(page_size or limit, limit or page_size),
            after=after,
            until=until,
            limit=limit,
            is_ascending=is_ascending,
        )

    @property
    def iterator_class(self):
        return SequencedItemIterator

    def get_most_recent_event(self, stored_entity_id, until=None, include_until=False):
        """
        Returns the most recent stored event for given entity ID.

        :rtype: OldDomainEvent, NoneType

        """
        events = self.get_most_recent_events(stored_entity_id, until=until, limit=1, include_until=include_until)
        try:
            return events[0]
        except IndexError:
            return None

    def get_most_recent_events(self, stored_entity_id, until=None, limit=None, include_until=False):
        """
        Returns an optionally limited number of the most recent stored events for a given entity ID.

        :rtype: list

        """
        return self.get_stored_events(
            stored_entity_id=stored_entity_id,
            until=until,
            limit=limit,
            query_ascending=False,
            results_ascending=False,
            include_until_when_descending=include_until,
        )

    def get_most_recent_integer_sequenced_events(self, sequence_id, until=None, limit=None, include_until=False):
        """
        Returns an optionally limited number of the most recent stored events for a given entity ID.

        :rtype: list

        """
        return self.get_integer_sequenced_items(sequence_id=sequence_id, lt=until, limit=limit, query_ascending=False,
                                                results_ascending=False)

    @staticmethod
    def make_entity_version_id(stored_entity_id, version):
        """
        Constructs entity version ID from stored entity ID and version number.

        :rtype: str

        """
        return u"{}::version::{}".format(stored_entity_id, version)

    @staticmethod
    def map(func, iterable):
        return six.moves.map(func, iterable)

    def raise_entity_version_not_found(self, stored_entity_id, version_number):
        raise EntityVersionNotFound(
            "Entity version '{}' for of stored entity '{}' not found."
            "".format(version_number, stored_entity_id)
        )
