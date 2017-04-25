from __future__ import absolute_import, division, print_function, unicode_literals

from uuid import uuid4

from eventsourcing.domain.model.entity import AbstractEntityRepository, Created, Discarded, \
    TimestampedVersionedEntity, entity_mutator
from eventsourcing.domain.model.events import TimestampedVersionedEntityEvent, mutator, publish


class Collection(TimestampedVersionedEntity):
    class Created(Created):
        def __init__(self, **kwargs):
            super(Collection.Created, self).__init__(**kwargs)

    class Discarded(Discarded):
        def __init__(self, **kwargs):
            super(Collection.Discarded, self).__init__(**kwargs)

    class ItemAdded(TimestampedVersionedEntityEvent):
        @property
        def item(self):
            return self.__dict__['item']

    class ItemRemoved(TimestampedVersionedEntityEvent):
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
        self._apply(event)
        publish(event)

    def remove_item(self, item):
        self._assert_not_discarded()
        event = self.ItemRemoved(
            originator_id=self.id,
            originator_version=self._version,
            item=item,
        )
        self._apply(event)
        publish(event)

    @staticmethod
    def _mutator(initial, event):
        return collection_mutator(initial, event)


def register_new_collection(collection_id=None):
    collection_id = uuid4().hex if collection_id is None else collection_id
    event = Collection.Created(originator_id=collection_id)
    entity = Collection.mutate(event=event)
    publish(event)
    return entity


@mutator
def collection_mutator(initial, event):
    return entity_mutator(initial, event)


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
