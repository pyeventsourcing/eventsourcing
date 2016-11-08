from eventsourcing.domain.model.entity import EventSourcedEntity, EntityRepository
from eventsourcing.domain.model.events import DomainEvent, publish
from eventsourcing.exceptions import RepositoryKeyError


class Sequence(EventSourcedEntity):

    def __init__(self, max_size=None, **kwargs):
        super(Sequence, self).__init__(**kwargs)
        self._max_size = max_size

    class Started(EventSourcedEntity.Created):
        """Occurs when sequence is started."""

    class Appended(DomainEvent):
        """Occurs when item is appended."""

    @property
    def name(self):
        return self.id

    @property
    def max_size(self):
        return self._max_size


def start_sequence(name, max_size=None):
    event = Sequence.Started(entity_id=name, max_size=max_size)
    entity = Sequence.mutate(event=event)
    publish(event)
    return entity


class SequenceRepository(EntityRepository):

    def get_or_create(self, sequence_name, sequence_max_size):
        """
        Gets or creates a log.

        :rtype: Log
        """
        try:
            return self[sequence_name]
        except RepositoryKeyError:
            return start_sequence(sequence_name, sequence_max_size)
