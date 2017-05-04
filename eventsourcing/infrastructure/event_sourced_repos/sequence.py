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

    def start(self, i, j, h, max_size=None):
        sequence_id = self.create_sequence_id(i, j)

        sequence = start_compound_sequence(sequence_id, i=i, j=j, h=h, max_size=max_size)
        return CompoundSequenceReader(sequence, self.event_store)

    def get_last_sequence(self, sequence):
        try:
            last = sequence[-1]
        except IndexError:
            return sequence
        else:
            if isinstance(last, UUID):
                return self.get_last_sequence(self.get_reader(last))
            else:
                return sequence

    def get_last_item(self, sequence):
        last_sequence = self.get_last_sequence(sequence)
        return last_sequence[-1]

    def demote(self, root, child, detached_id=None):
        i = 0  # always zero, because always demote the apex
        j = child.j * child.max_size  # N**h
        h = child.h + 1
        new_child = self.start(i, j, h, max_size=child.max_size)
        # First, append child to new child.
        new_child.append(child.id)
        # Attach new branch.
        if detached_id is not None:
            new_child.append(detached_id)
        # Then append new child to to root.
        root.append(new_child.id)
        return new_child

    def extend_base(self, left, item):
        i = left.j
        j = i + left.max_size
        h = left.h
        new = self.start(i, j, h, max_size=left.max_size)
        # Append an item to new child.
        new.append(item)

        return new

    def calc_parent_i_j_h(self, child6):
        N = child6.max_size
        n_c = child6.i // N
        n_p = n_c // N
        h_p = child6.h + 1
        width_p = N ** h_p
        i = n_p * width_p
        j = i + width_p
        h = child6.h + 1
        return i, j, h
