from collections import namedtuple

SequencedItem = namedtuple('SequencedItem', ['sequence_id', 'position', 'topic', 'state'])

StoredEvent = namedtuple('StoredEvent', ['originator_id', 'originator_version', 'topic', 'state'])


class SequencedItemFieldNames(object):
    def __init__(self, sequenced_item_class):
        self._field_names = sequenced_item_class._fields

    @property
    def sequence_id(self):
        # Sequence ID is assumed to be the first field of a sequenced item.
        return self._field_names[0]

    @property
    def position(self):
        # Position is assumed to be the second field of a sequenced item.
        return self._field_names[1]

    @property
    def topic(self):
        # Topic is assumed to be the third field of a sequenced item.
        return self._field_names[2]

    @property
    def state(self):
        # State is assumed to be the fourth field of a sequenced item.
        return self._field_names[3]

    @property
    def other_names(self):
        return self._field_names[4:]

    def __getitem__(self, i):
        return self._field_names[i]
