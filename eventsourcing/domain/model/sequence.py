from eventsourcing.domain.model.entity import AbstractEntityRepository, Created, TimestampedVersionedEntity
from eventsourcing.domain.model.events import publish
from eventsourcing.exceptions import RepositoryKeyError


class Sequence(TimestampedVersionedEntity):
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
        super(Sequence, self).__init__(**kwargs)
        self._max_size = max_size

    @property
    def max_size(self):
        return self._max_size


class CompoundSequence(Sequence):
    pass


def start_sequence(sequence_id, max_size=None):
    """
    Factory for Sequence objects.
    
    :rtype: Sequence
    """
    event = Sequence.Started(originator_id=sequence_id, max_size=max_size)
    entity = Sequence._mutate(initial=None, event=event)
    publish(event)
    return entity


def start_compound_sequence(sequence_id, max_size=None):
    """
    Factory for Sequence objects.
    
    :rtype: Sequence
    """
    event = CompoundSequence.Started(originator_id=sequence_id, max_size=max_size)
    entity = CompoundSequence._mutate(initial=None, event=event)
    publish(event)
    return entity


class SequenceRepository(AbstractEntityRepository):
    """
    Repository for sequence objects.
    """
    def get_or_create(self, sequence_id, max_size=None):
        """
        Gets or creates a sequence.

        :rtype: Sequence
        """
        try:
            sequence = self[sequence_id]
        except RepositoryKeyError:
            sequence = start_sequence(sequence_id, max_size=max_size)
        return sequence


class CompoundSequenceRepository(AbstractEntityRepository):
    """
    Repository for compound sequence objects.
    """
    def get_or_create(self, sequence_id, max_size=None):
        """
        Gets or creates a sequence.

        :rtype: Sequence
        """
        try:
            sequence = self[sequence_id]
        except RepositoryKeyError:
            sequence = start_compound_sequence(sequence_id, max_size=max_size)
        return sequence
