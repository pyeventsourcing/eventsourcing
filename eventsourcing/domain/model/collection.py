from __future__ import absolute_import, division, print_function, unicode_literals

from eventsourcing.domain.model.entity import TimestampedVersionedEntity, TTimestampedVersionedEntity
from eventsourcing.infrastructure.base import AbstractEntityRepository


class Collection(TimestampedVersionedEntity):
    class Event(TimestampedVersionedEntity.Event[TTimestampedVersionedEntity]):
        """Supertype for events of collection entities."""

    class Created(
        Event[TTimestampedVersionedEntity], TimestampedVersionedEntity.Created[TTimestampedVersionedEntity]
    ):
        """Published when collection is created."""

    class Discarded(
        Event[TTimestampedVersionedEntity], TimestampedVersionedEntity.Discarded[TTimestampedVersionedEntity]
    ):
        """Published when collection is discarded."""

    class EventWithItem(Event[TTimestampedVersionedEntity]):
        @property
        def item(self):
            return self.__dict__["item"]

    class ItemAdded(EventWithItem):
        def mutate(self, obj: "Collection") -> None:
            obj._items.add(self.item)

    class ItemRemoved(EventWithItem):
        def mutate(self, obj: "Collection") -> None:
            obj._items.remove(self.item)

    def __init__(self, **kwargs):
        super(Collection, self).__init__(**kwargs)
        self._items = set()

    def __iter__(self):
        return self._items.__iter__()

    @property
    def items(self):
        self.__assert_not_discarded__()
        return self._items

    def add_item(self, item):
        self.__trigger_event__(self.ItemAdded, item=item)

    def remove_item(self, item):
        self.__trigger_event__(self.ItemRemoved, item=item)


def register_new_collection(collection_id=None):
    return Collection.__create__(originator_id=collection_id)


class AbstractCollectionRepository(AbstractEntityRepository):
    pass
