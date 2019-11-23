from __future__ import absolute_import, division, print_function, unicode_literals

from eventsourcing.domain.model.entity import TimestampedVersionedEntity, T_en_tim_ver
from eventsourcing.types import AbstractEntityRepository


class Collection(TimestampedVersionedEntity):
    class Event(TimestampedVersionedEntity.Event[T_en_tim_ver]):
        """Supertype for events of collection entities."""

    class Created(
        Event[T_en_tim_ver], TimestampedVersionedEntity.Created[T_en_tim_ver]
    ):
        """Published when collection is created."""

    class Discarded(
        Event[T_en_tim_ver], TimestampedVersionedEntity.Discarded[T_en_tim_ver]
    ):
        """Published when collection is discarded."""

    class EventWithItem(Event[T_en_tim_ver]):
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
