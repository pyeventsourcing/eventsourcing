import six

from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.entity import AbstractEntityRepository, TimestampedVersionedEntity
from eventsourcing.domain.model.events import publish
from eventsourcing.exceptions import ConcurrencyError, RepositoryKeyError, SequenceFullError


class SequenceMeta(TimestampedVersionedEntity):
    """
    This class represents an overall, which is
    initially empty. A specialised repository
    SequenceRepo returns a Sequence object which
    can append items to the sequence without
    loading all the events. It can also index,
    slice and iterate through items in the sequence
    without having to load all of them.
    """

    class Event(TimestampedVersionedEntity.Event):
        """Layer supertype."""

    class Started(Event, TimestampedVersionedEntity.Created):
        """Occurs when sequence is started."""

    class ItemAppended(Event):
        """Occurs when item is appended to a sequence."""

    def __init__(self, max_size=None, **kwargs):
        super(SequenceMeta, self).__init__(**kwargs)
        self._max_size = max_size

    @property
    def max_size(self):
        return self._max_size


class CompoundSequence(SequenceMeta):
    def __init__(self, i=None, j=None, h=None, *args, **kwargs):
        super(CompoundSequence, self).__init__(*args, **kwargs)
        self._i = i
        self._j = j
        self._h = h

    @property
    def i(self):
        return self._i

    @property
    def j(self):
        return self._j

    @property
    def h(self):
        return self._h


def start_compound_sequence(sequence_id, i, j, h, max_size):
    """
    Factory for Sequence objects.
    
    :rtype: SequenceMeta
    """
    event = CompoundSequence.Started(originator_id=sequence_id, i=i, j=j, h=h, max_size=max_size)
    entity = CompoundSequence._mutate(initial=None, event=event)
    publish(event)
    return entity


class Sequence(object):
    def __init__(self, sequence_id, repo):
        assert isinstance(repo, AbstractSequenceRepository)
        self._id = sequence_id
        self._repo = repo
        self._meta = None

    @property
    def id(self):
        return self._id

    @property
    def meta(self):
        if self._meta is None:
            self._meta = self._repo.get_entity(self._id)
        return self._meta

    def append(self, item):
        """
        Appends item to sequence, by publishing an ItemAppended event.

        Won't overrun the end of the sequence, because the position is
        fixed to be less than the max_size, won't overwrite due to OCC.
        """
        next_version = self.get_next_version()
        if self.meta.max_size and self.meta.max_size < next_version:
            raise SequenceFullError
        event = SequenceMeta.ItemAppended(
            originator_id=self.id,
            originator_version=next_version,
            item=item,
        )
        publish(event)

    @retry(ConcurrencyError)
    def get_next_version(self):
        last_event = self._repo.event_store.get_most_recent_event(self.id)
        if last_event is None:
            self.register_sequence(self.id)
            next_version = 1
        else:
            next_version = last_event.originator_version + 1
        return next_version

    def register_sequence(self, sequence_id):
        """
        Factory for Sequence objects.

        :rtype: SequenceMeta
        """
        event = SequenceMeta.Started(originator_id=sequence_id, max_size=self._repo.sequence_size)
        entity = SequenceMeta._mutate(initial=None, event=event)
        publish(event)
        self._meta = entity

    def __getitem__(self, item):
        assert isinstance(item, (six.integer_types, slice))
        sequence_len = None
        if isinstance(item, six.integer_types):
            if item < 0:
                if sequence_len is None:
                    sequence_len = len(self)
                index = sequence_len + item
                if index < 0:
                    raise IndexError("Sequence index out of range: {}".format(item))
            else:
                index = item
            event = self._repo.event_store.get_domain_event(originator_id=self.id, eq=index + 1)
            return event.item
        elif isinstance(item, slice):
            assert item.step == None, "Slice step must be 1: {}".format(str(item.step))
            if item.start is None:
                start_index = 0
            elif item.start < 0:
                if sequence_len is None:
                    sequence_len = len(self)
                start_index = max(sequence_len + item.start, 0)
            else:
                start_index = item.start

            if not isinstance(item.stop, six.integer_types):
                limit = None
            elif item.stop < 0:
                if sequence_len is None:
                    sequence_len = len(self)
                limit = sequence_len + item.stop - start_index
            else:
                limit = item.stop - start_index

            if limit is not None and limit <= 0:
                return []

            events = self._repo.event_store.get_domain_events(originator_id=self.id,
                                                        gte=start_index + 1, limit=limit)
            items = [e.item for e in events]
            return items

    def __len__(self):
        """
        Counts items in sequence.
        """
        events = self._repo.event_store.get_domain_events(originator_id=self.id, limit=1,
                                                    is_ascending=False)
        return events[0].originator_version

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.id == other.id



class AbstractSequenceRepository(AbstractEntityRepository):
    """
    Repository for sequence objects.
    """

    def __init__(self, sequence_size):
        self.sequence_size = sequence_size

    @retry(ConcurrencyError, max_retries=1, wait=0)
    def get_or_create(self, sequence_id, max_size=None):
        """
        Gets or creates a sequence.
        
        Gets first because mostly they will exist.
        
        Decorated with a retry for ConcurrencyError to deal
        with race condition on creating after failing to get.

        :rtype: SequenceMeta
        """
        raise Exception("Remove this method, safely")
        try:
            sequence = self[sequence_id]
        except RepositoryKeyError:
            sequence = start_sequence(sequence_id, max_size=max_size)
        return sequence


class AbstractCompoundSequenceRepository(AbstractEntityRepository):
    """
    Repository for compound sequence objects.
    """
