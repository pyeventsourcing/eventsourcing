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


def start_sequence(name):
    """
    Factory for Sequence objects.
    
    :rtype: Sequence
    """
    event = Sequence.Started(originator_id=name)
    entity = Sequence._mutate(initial=None, event=event)
    publish(event)
    return entity


class SequenceRepository(AbstractEntityRepository):
    """
    Repository for sequence objects.
    """
    def get_or_create(self, sequence_id):
        """
        Gets or creates a sequence.

        :rtype: Sequence
        """
        try:
            sequence = self[sequence_id]
        except RepositoryKeyError:
            sequence = start_sequence(sequence_id)
        return sequence
