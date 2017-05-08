import six

from eventsourcing.domain.model.events import publish
from eventsourcing.domain.model.sequence import SequenceMeta
from eventsourcing.exceptions import SequenceFullError
from eventsourcing.infrastructure.eventstore import AbstractEventStore


class SequenceReader(object):
    def __init__(self, sequence, event_store):
        assert isinstance(sequence, SequenceMeta), sequence
        assert isinstance(event_store, AbstractEventStore), event_store
        self.sequence = sequence
        self.event_store = event_store
        self.max_size = sequence.max_size

    @property
    def id(self):
        return self.sequence.id



class CompoundSequenceReader(SequenceReader):
    @property
    def i(self):
        return self.sequence.i

    @property
    def j(self):
        return self.sequence.j

    @property
    def h(self):
        return self.sequence.h
