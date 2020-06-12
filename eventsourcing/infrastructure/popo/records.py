from typing import Any, NamedTuple


class IntegerSequencedRecord(object):
    """
    Encapsulates sequenced item tuple (containing real event object).
    """
    def __init__(self, sequenced_item: NamedTuple):
        self.sequenced_item = sequenced_item

    def __getattr__(self, item: str) -> Any:
        return getattr(self.sequenced_item, item)


class SnapshotRecord(IntegerSequencedRecord):
    pass


class StoredEventRecord(IntegerSequencedRecord):
    """
    Encapsulates sequenced item tuple (containing real event object).

    Allows other attributes to be set, such as notification ID.
    """
    notification_id = None
    application_name = None
