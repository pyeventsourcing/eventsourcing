from __future__ import absolute_import, division, print_function, unicode_literals

from typing import Optional, cast

from eventsourcing.domain.model.entity import TimestampedVersionedEntity
from eventsourcing.types import AbstractEntityRepository, T


class Collection(TimestampedVersionedEntity[T]):
    class Event(TimestampedVersionedEntity.Event[T]):
        """Supertype for events of collection entities."""

    class Created(Event[T], TimestampedVersionedEntity.Created[T]):
        """Published when collection is created."""

    class Discarded(Event[T], TimestampedVersionedEntity.Discarded[T]):
        """Published when collection is discarded."""

    class EventWithItem(Event[T]):
        @property
        def item(self):
            return self.__dict__["item"]

    class ItemAdded(EventWithItem[T]):
        def __mutate__(self, obj: Optional[T]) -> Optional[T]:
            obj = super(Collection.ItemAdded, self).__mutate__(obj)
            collection = cast(Collection, obj)
            collection._items.add(self.item)
            return obj

    class ItemRemoved(EventWithItem[T]):
        def __mutate__(self, obj: Optional[T]) -> Optional[T]:
            obj = super(Collection.ItemRemoved, self).__mutate__(obj)
            collection = cast(Collection, obj)
            collection._items.remove(self.item)
            return obj

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
