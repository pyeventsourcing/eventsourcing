from uuid import UUID, uuid5

from eventsourcing.domain.model.sequence import Sequence, SequenceRepository, CompoundSequenceRepository, \
    CompoundSequence, start_compound_sequence
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.sequencereader import SequenceReader, CompoundSequenceReader


class SequenceRepo(EventSourcedRepository, SequenceRepository):
    mutator = Sequence._mutate

    def get_entity(self, entity_id, lt=None, lte=None):
        """
        Replays entity using only the 'Started' event.
        
        :rtype: Sequence
        """
        return self.event_player.replay_entity(entity_id, limit=1)

    def get_reader(self, sequence_id, max_size=None):
        """
        Returns a sequence reader for the given sequence_id.
        
        Starts sequence entity if it doesn't exist.
        
        :rtype: SequenceReader 
        """
        return SequenceReader(
            sequence=self.get_or_create(sequence_id, max_size=max_size),
            event_store=self.event_store,
        )


class CompoundSequenceRepo(EventSourcedRepository, CompoundSequenceRepository):
    mutator = CompoundSequence._mutate

    def get_entity(self, entity_id, lt=None, lte=None):
        """
        Replays entity using only the 'Started' event.
        
        :rtype: Sequence
        """
        return self.event_player.replay_entity(entity_id, limit=1)

    def get_reader(self, sequence_id, max_size=None):
        """
        Returns a sequence reader for the given sequence_id.
        
        Starts sequence entity if it doesn't exist.
        
        :rtype: SequenceReader 
        """
        return CompoundSequenceReader(
            sequence=self.get_or_create(sequence_id, max_size=max_size),
            event_store=self.event_store,
        )

    def create_sequence_id(self, i, j):
        namespace = UUID('00000000-0000-0000-0000-000000000000')
        return uuid5(namespace, str((i, j)))

    def start(self, i, j, max_size=None):
        sequence_id = self.create_sequence_id(i, j)

        sequence = start_compound_sequence(sequence_id, max_size=max_size)
        return CompoundSequenceReader(sequence, self.event_store)
