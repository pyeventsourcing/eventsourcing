from __future__ import absolute_import, division, print_function, unicode_literals

from uuid import uuid4

from eventsourcing.domain.model.entity import AbstractEntityRepository, Created, Discarded, \
    TimestampedVersionedEntity, entity_mutator, singledispatch
from eventsourcing.domain.model.events import TimestampedVersionedEntityEvent, publish


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
    def _mutator(event, initial):
        return collection_mutator(event, initial)


def register_new_collection(collection_id=None):
    collection_id = uuid4().hex if collection_id is None else collection_id
    event = Collection.Created(originator_id=collection_id)
    entity = Collection.mutate(event=event)
    publish(event)
    return entity


@singledispatch
def collection_mutator(event, initial):
    return entity_mutator(event, initial)


@collection_mutator.register(Collection.ItemAdded)
def collection_item_added_mutator(event, entity):
    assert isinstance(entity, Collection)
    entity._items.add(event.item)
    entity._increment_version()
    return entity


@collection_mutator.register(Collection.ItemRemoved)
def collection_item_removed_mutator(event, entity):
    entity._items.remove(event.item)
    entity._increment_version()
    return entity


class AbstractCollectionRepository(AbstractEntityRepository):
    pass
