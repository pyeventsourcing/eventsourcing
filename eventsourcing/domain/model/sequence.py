from eventsourcing.domain.model.entity import TimestampedVersionedEntity, AbstractEntityRepository, Created
from eventsourcing.domain.model.events import publish, TimestampedVersionedEntityEvent
from eventsourcing.exceptions import RepositoryKeyError


class Sequence(TimestampedVersionedEntity):

    class Started(Created):
        """Occurs when sequence is started."""

    class Appended(TimestampedVersionedEntityEvent):
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
