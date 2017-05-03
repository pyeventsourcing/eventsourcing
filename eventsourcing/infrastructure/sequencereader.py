import six

from eventsourcing.domain.model.events import publish
from eventsourcing.domain.model.sequence import Sequence
from eventsourcing.exceptions import SequenceFullError
from eventsourcing.infrastructure.eventstore import AbstractEventStore


class SequenceReader(object):
    def __init__(self, sequence, event_store, max_size=None):
        assert isinstance(sequence, Sequence), sequence
        assert isinstance(event_store, AbstractEventStore), event_store
        self.sequence = sequence
        self.event_store = event_store
        self.max_size = max_size

    @property
    def id(self):
        return self.sequence.id

    def __getitem__(self, item):
        assert isinstance(item, (six.integer_types, slice))
        sequence_len = None
        if isinstance(item, six.integer_types):
            if item < 0:
                if sequence_len is None:
                    sequence_len = len(self)
                index = sequence_len + item
                if index < 0:
                    raise IndexError("Sequence index out of range: {}".format(item))
            else:
                index = item
            event = self.event_store.get_domain_event(originator_id=self.sequence.id, eq=index + 1)
            return event.item
        elif isinstance(item, slice):
            assert item.step == None, "Slice step must be 1: {}".format(str(item.step))
            if item.start is None:
                start_index = 0
            elif item.start < 0:
                if sequence_len is None:
                    sequence_len = len(self)
                start_index = max(sequence_len + item.start, 0)
            else:
                start_index = item.start

            if not isinstance(item.stop, six.integer_types):
                limit = None
            elif item.stop < 0:
                if sequence_len is None:
                    sequence_len = len(self)
                limit = sequence_len + item.stop - start_index
            else:
                limit = item.stop - start_index

            if limit is not None and limit <= 0:
                return []

            events = self.event_store.get_domain_events(originator_id=self.sequence.id,
                                                        gte=start_index + 1, limit=limit)
            items = [e.item for e in events]
            return items

    def __len__(self):
        """
        Counts items in sequence.
        """
        events = self.event_store.get_domain_events(originator_id=self.sequence.id, limit=1,
                                                    is_ascending=False)
        return events[0].originator_version

    def append(self, item):
        """
        Appends item to sequence, by publishing an ItemAppended event.
        """
        last_event = self.event_store.get_most_recent_event(self.id)
        next_version = last_event.originator_version + 1
        if self.max_size and self.max_size < next_version:
            raise SequenceFullError
        event = Sequence.ItemAppended(
            originator_id=self.id,
            originator_version=next_version,
            item=item,
        )
        publish(event)
