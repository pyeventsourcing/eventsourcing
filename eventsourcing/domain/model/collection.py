from __future__ import absolute_import, unicode_literals, division, print_function

from uuid import uuid4

from eventsourcing.domain.model.entity import EntityRepository
from eventsourcing.domain.model.events import DomainEvent, publish
from eventsourcing.domain.model.entity import EventSourcedEntity


class Collection(EventSourcedEntity):
    class Created(EventSourcedEntity.Created):
        def __init__(self, **kwargs):
            super(Collection.Created, self).__init__(**kwargs)

        def mutate_collection(self, event, entity):
            entity._items.add(event.item)
            entity._increment_version()
            return entity

    class Discarded(EventSourcedEntity.Discarded):
        def __init__(self, **kwargs):
            super(Collection.Discarded, self).__init__(**kwargs)

        def mutate_collection(self, event, entity):
            entity._items.remove(event.item)
            entity._increment_version()
            return entity


    class ItemAdded(DomainEvent):
        @property
        def item(self):
            return self.__dict__['item']

    class ItemRemoved(DomainEvent):
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
            entity_id=self.id,
            entity_version=self._version,
            item=item,
        )
        self._apply(event)
        publish(event)

    def remove_item(self, item):
        self._assert_not_discarded()
        event = self.ItemRemoved(
            entity_id=self.id,
            entity_version=self._version,
            item=item,
        )
        self._apply(event)
        publish(event)

    @classmethod
    def mutate(cls, entity=None, event=None):
        if not hasattr(event, 'mutate_collection'):
            msg = "{} does not provide a mutate_collection() method.".format(event.__class__)
            raise NotImplementedError(msg)

        entity = event.mutate_collection(event, entity or cls)
        entity._increment_version()
        return entity

def register_new_collection(collection_id=None):
    collection_id = uuid4().hex if collection_id is None else collection_id
    event = Collection.Created(entity_id=collection_id)
    entity = Collection.mutate(event=event)
    publish(event)
    return entity


class CollectionRepository(EntityRepository):
    pass
