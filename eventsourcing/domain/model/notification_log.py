from singledispatch import singledispatch

from eventsourcing.domain.model.entity import EventSourcedEntity, EntityRepository, entity_mutator
from eventsourcing.domain.model.events import DomainEvent, publish
# from eventsourcing.domain.model.log import Log
# from eventsourcing.domain.model.sequence import Sequence
# from eventsourcing.exceptions import LogFullError

# Todo: New idea, just make it be a mixture of an archived log to hold the current sequence and a sequence.
# class NotificationLog(Log, Sequence):


class NotificationLog(EventSourcedEntity):
    # Add items, up to log size, then empty this, create a snapshot at that version, create an archived log page
    # with the data until that version.
    # Get pages of items using predictable keys (entity ID), starting from the current log.
    # Get pages of items using predictable keys (entity ID), starting from item 0.
    # Entity ID = log name + id_start + , + id_end.

    class Started(EventSourcedEntity.Created):
        pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged):
        pass

    # class ItemAdded(DomainEvent):
    #     pass
    #
    # class Closed(DomainEvent):
    #     @property
    #     def message(self):
    #         return self.__dict__['message']

    def __init__(self, name, sequence_max_size=None, **kwargs):
        super(NotificationLog, self).__init__(**kwargs)
        self._name = name
        self._sequence_max_size = sequence_max_size

    @property
    def name(self):
        return self._name

    @property
    def sequence_max_size(self):
        return self._sequence_max_size

    @staticmethod
    def _mutator(event, initial):
        return notification_log_mutator(event, initial)


@singledispatch
def notification_log_mutator(event, initial):
    return entity_mutator(event, initial)


# @notification_log_mutator.register(NotificationLog.ItemAdded)
# def item_added_mutator(event, self):
#     assert isinstance(self, NotificationLog)
#     self._assert_not_discarded()
#     assert isinstance(event, NotificationLog.ItemAdded), event
#     assert isinstance(self, NotificationLog)
#     self.items.append(event.item)
#     self._increment_version()
#     return self
#
#
# @notification_log_mutator.register(NotificationLog.Closed)
# def item_added_mutator(event, self):
#     assert isinstance(event, NotificationLog.Closed), event
#     assert isinstance(self, NotificationLog)
#     return self


class NotificationLogRepository(EntityRepository):
    pass


def start_notification_log(log_name, sequence_max_size=100000):
    event = NotificationLog.Started(entity_id=log_name, name=log_name, sequence_max_size=sequence_max_size)
    entity = NotificationLog.mutate(event=event)
    publish(event)
    return entity
