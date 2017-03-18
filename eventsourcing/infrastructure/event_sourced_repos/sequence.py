from eventsourcing.domain.model.sequence import SequenceRepository, Sequence
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


class SequenceRepo(EventSourcedRepository, SequenceRepository):
    domain_class = Sequence

    def get_entity(self, entity_id, until=None):
        """
        Replays entity using only the 'Started' event.
        """
        return self.event_player.replay_entity(entity_id, limit=1)
