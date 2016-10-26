from singledispatch import singledispatch

from eventsourcing.domain.model.entity import EventSourcedEntity, EntityRepository, entity_mutator
from eventsourcing.domain.model.events import DomainEvent, publish


class ArchivedLog(EventSourcedEntity):
    # Add items, up to log size, then empty this, create a snapshot at that version, create an archived log page
    # with the data until that version.
    # Get pages of items using predictable keys (entity ID), starting from the current log.
    # Get pages of items using predictable keys (entity ID), starting from item 0.
    # Entity ID = log name + id_start + , + id_end.

    class Created(EventSourcedEntity.Created):
        pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged):
        pass

    class ItemAdded(DomainEvent):
        pass

    class Closed(DomainEvent):
        @property
        def message(self):
            return self.__dict__['message']

    def __init__(self, name, size=None, **kwargs):
        super(ArchivedLog, self).__init__(**kwargs)
        self._name = name
        self._size = size
        self._items = []

    @property
    def log_size(self):
        return self._size

    @property
    def name(self):
        return self._name

    @property
    def items(self):
        return self._items

    def add_item(self, item):
        self._assert_not_discarded()
        if len(self.items) < self._size - 1:
            event = ArchivedLog.ItemAdded(entity_id=self.id, entity_version=self.version, item=item)
        else:
            event = ArchivedLog.Closed(entity_id=self.id, entity_version=self.version, items=self.items + [item])
        self._apply(event)
        publish(event)

    @staticmethod
    def _mutator(event, initial):
        return archived_log_mutator(event, initial)


@singledispatch
def archived_log_mutator(event, initial):
    return entity_mutator(event, initial)


@archived_log_mutator.register(ArchivedLog.ItemAdded)
def item_added_mutator(event, self):
    assert isinstance(event, ArchivedLog.ItemAdded), event
    assert isinstance(self, ArchivedLog)
    self.items.append(event.item)
    return self


@archived_log_mutator.register(ArchivedLog.Closed)
def item_added_mutator(event, self):
    assert isinstance(event, ArchivedLog.Closed), event
    assert isinstance(self, ArchivedLog)
    self._items = []
    return self


class ArchivedLogRepository(EntityRepository):
    pass


def create_archived_log(log_name, log_size):
    entity_id = make_current_archived_log_id(log_name)
    event = ArchivedLog.Created(entity_id=entity_id, name=log_name, size=log_size)
    entity = ArchivedLog.mutate(event=event)
    publish(event)
    return entity


def make_current_archived_log_id(log_name):
    return "{}::current".format(log_name, 'current')
