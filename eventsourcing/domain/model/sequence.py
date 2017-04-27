from eventsourcing.domain.model.entity import AbstractEntityRepository, Created, TimestampedVersionedEntity
from eventsourcing.domain.model.events import publish
from eventsourcing.exceptions import RepositoryKeyError


class Sequence(TimestampedVersionedEntity):
    class Event(TimestampedVersionedEntity.Event):
        """Layer supertype."""

    class Started(Event, TimestampedVersionedEntity.Created):
        """Occurs when sequence is started."""

    class ItemAppended(Event):
        """Occurs when item is appended."""

    @property
    def name(self):
        return self.id


def start_sequence(name):
    event = Sequence.Started(originator_id=name)
    entity = Sequence.mutate(event=event)
    publish(event)
    return entity


class SequenceRepository(AbstractEntityRepository):
    def get_or_create(self, sequence_name):
        """
        Gets or creates a log.

        :rtype: Timebucketedlog
        """
        try:
            return self[sequence_name]
        except RepositoryKeyError:
            return start_sequence(sequence_name)
