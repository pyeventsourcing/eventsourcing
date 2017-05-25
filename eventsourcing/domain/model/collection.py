from __future__ import absolute_import, division, print_function, unicode_literals

from uuid import uuid4

from eventsourcing.domain.model.decorators import mutator
from eventsourcing.domain.model.entity import AbstractEntityRepository, TimestampedVersionedEntity, mutate_entity
from eventsourcing.domain.model.events import publish


class Collection(TimestampedVersionedEntity):
    class Event(TimestampedVersionedEntity.Event):
        """Layer supertype."""

    class Created(Event, TimestampedVersionedEntity.Created):
        """Published when collection is created."""

    class Discarded(Event, TimestampedVersionedEntity.Discarded):
        """Published when collection is discarded."""

    class ItemAdded(Event):
        @property
        def item(self):
            return self.__dict__['item']

    class ItemRemoved(Event):
        @property
        def item(self):
            return self.__dict__['item']

    def __init__(self, **kwargs):
        super(Collection, self).__init__(**kwargs)
        self._items = set()

    def __iter__(self):
        return self._items.__iter__()

    @property
    def items(self):
        self._assert_not_discarded()
        return self._items

    def add_item(self, item):
        self._assert_not_discarded()
        event = self.ItemAdded(
            originator_id=self.id,
            originator_version=self._version,
            item=item,
        )
        self._apply_and_publish(event)

    def remove_item(self, item):
        self._assert_not_discarded()
        event = self.ItemRemoved(
            originator_id=self.id,
            originator_version=self._version,
            item=item,
        )
        self._apply_and_publish(event)

    @classmethod
    def _mutate(cls, initial, event):
        return collection_mutator(initial or cls, event)


def register_new_collection(collection_id=None):
    collection_id = uuid4().hex if collection_id is None else collection_id
    event = Collection.Created(originator_id=collection_id)
    entity = collection_mutator(Collection, event)
    publish(event)
    return entity


@mutator
def collection_mutator(initial, event):
    return mutate_entity(initial, event)


@collection_mutator.register(Collection.ItemAdded)
def collection_item_added_mutator(self, event):
    assert isinstance(self, Collection)
    self._items.add(event.item)
    self._increment_version()
    return self


@collection_mutator.register(Collection.ItemRemoved)
def collection_item_removed_mutator(self, event):
    self._items.remove(event.item)
    self._increment_version()
    return self


class AbstractCollectionRepository(AbstractEntityRepository):
    pass
