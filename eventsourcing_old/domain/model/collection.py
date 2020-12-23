from typing import Any, Iterator, Optional, Set
from uuid import UUID

from eventsourcing.domain.model.entity import (
    TimestampedVersionedEntity,
    TTimestampedVersionedEntity,
)
from eventsourcing.domain.model.repository import AbstractEntityRepository


class Collection(TimestampedVersionedEntity):
    class Event(TimestampedVersionedEntity.Event[TTimestampedVersionedEntity]):
        """Supertype for events of collection entities."""

    class Created(
        Event[TTimestampedVersionedEntity],
        TimestampedVersionedEntity.Created[TTimestampedVersionedEntity],
    ):
        """Published when collection is created."""

    class Discarded(
        Event[TTimestampedVersionedEntity],
        TimestampedVersionedEntity.Discarded[TTimestampedVersionedEntity],
    ):
        """Published when collection is discarded."""

    class EventWithItem(Event[TTimestampedVersionedEntity]):
        @property
        def item(self) -> Any:
            return self.__dict__["item"]

    def __init__(self, **kwargs: Any):
        super(Collection, self).__init__(**kwargs)
        self._items: Set = set()

    def __iter__(self) -> Iterator:
        return self._items.__iter__()

    @property
    def items(self) -> Set:
        self.__assert_not_discarded__()
        return self._items

    def add_item(self, item: Any) -> None:
        self.__trigger_event__(self.ItemAdded, item=item)

    class ItemAdded(EventWithItem):
        def mutate(self, obj: "Collection") -> None:
            obj._items.add(self.item)

    def remove_item(self, item: Any) -> None:
        self.__trigger_event__(self.ItemRemoved, item=item)

    class ItemRemoved(EventWithItem):
        def mutate(self, obj: "Collection") -> None:
            obj._items.remove(self.item)


def register_new_collection(collection_id: Optional[UUID] = None) -> Collection:
    return Collection.__create__(originator_id=collection_id)


class AbstractCollectionRepository(AbstractEntityRepository):
    pass
