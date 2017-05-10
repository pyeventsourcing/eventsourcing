from eventsourcing.domain.model.sequence import AbstractCompoundSequenceRepository, AbstractSequenceRepository, \
    CompoundSequence, CompoundSequenceMeta, Sequence, SequenceMeta
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
from eventsourcing.infrastructure.sequencereader import SequenceReader


class SequenceRepository(EventSourcedRepository, AbstractSequenceRepository):
    mutator = SequenceMeta._mutate

    def __getitem__(self, sequence_id):
        """
        Returns sequence for given ID.
        """
        return Sequence(sequence_id=sequence_id, repo=self)

    def get_entity(self, entity_id, lt=None, lte=None):
        """
        Replays entity using only the 'Started' event.
        
        :rtype: SequenceMeta
        """
        return self.event_player.replay_entity(entity_id, limit=1)

    # Todo: Factor this out?
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


class CompoundSequenceRepository(SequenceRepository, AbstractCompoundSequenceRepository):
    mutator = CompoundSequenceMeta._mutate
    subrepo_class = SequenceRepository

    def __init__(self, *args, **kwargs):
        super(CompoundSequenceRepository, self).__init__(*args, **kwargs)
        self._subrepo = self.subrepo_class(
            event_store=self.event_store,
            sequence_size=self.sequence_size,
        )

    @property
    def subrepo(self):
        return self._subrepo

    def __getitem__(self, sequence_id):
        """
        Returns sequence for given ID.
        """
        return CompoundSequence(sequence_id=sequence_id, repo=self, subrepo=self.subrepo)
