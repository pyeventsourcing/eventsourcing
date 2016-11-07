from singledispatch import singledispatch

from eventsourcing.domain.model.entity import EventSourcedEntity, EntityRepository, entity_mutator
from eventsourcing.domain.model.events import DomainEvent, publish
from eventsourcing.domain.model.sequence import start_sequence
from eventsourcing.exceptions import LogFullError


class NotificationLog(EventSourcedEntity):
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
        super(NotificationLog, self).__init__(**kwargs)
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
        if len(self.items) < self._size:
            event = NotificationLog.ItemAdded(entity_id=self.id, entity_version=self.version, item=item)
        else:
            raise LogFullError()
        self._apply(event)
        publish(event)

    @staticmethod
    def _mutator(event, initial):
        return notification_log_mutator(event, initial)


@singledispatch
def notification_log_mutator(event, initial):
    return entity_mutator(event, initial)


@notification_log_mutator.register(NotificationLog.ItemAdded)
def item_added_mutator(event, self):
    assert isinstance(self, NotificationLog)
    self._assert_not_discarded()
    assert isinstance(event, NotificationLog.ItemAdded), event
    assert isinstance(self, NotificationLog)
    self.items.append(event.item)
    self._increment_version()
    return self


@notification_log_mutator.register(NotificationLog.Closed)
def item_added_mutator(event, self):
    assert isinstance(event, NotificationLog.Closed), event
    assert isinstance(self, NotificationLog)
    return self


class NotificationLogRepository(EntityRepository):
    pass


def create_notification_log(log_name, size=100000):
    # Create a sequence for it.
    start_sequence(log_name)

    event = NotificationLog.Created(entity_id=log_name, name=log_name, size=size)
    entity = NotificationLog.mutate(event=event)
    publish(event)

    return entity
