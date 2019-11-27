from collections import namedtuple
from typing import NamedTuple, Tuple, Type

SequencedItem = namedtuple(
    "SequencedItem", ["sequence_id", "position", "topic", "state"]
)

StoredEvent = namedtuple(
    "StoredEvent", ["originator_id", "originator_version", "topic", "state"]
)


class SequencedItemFieldNames(object):
    def __init__(self, sequenced_item_class: Type[NamedTuple]):
        self._field_names = sequenced_item_class._fields

    @property
    def sequence_id(self) -> str:
        # Sequence ID is assumed to be the first field of a sequenced item.
        return self._field_names[0]

    @property
    def position(self) -> str:
        # Position is assumed to be the second field of a sequenced item.
        return self._field_names[1]

    @property
    def topic(self) -> str:
        # Topic is assumed to be the third field of a sequenced item.
        return self._field_names[2]

    @property
    def state(self) -> str:
        # State is assumed to be the fourth field of a sequenced item.
        return self._field_names[3]

    @property
    def other_names(self) -> Tuple[str, ...]:
        return self._field_names[4:]

    def __getitem__(self, i: int) -> str:
        return self._field_names[i]
