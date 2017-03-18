from abc import ABCMeta, abstractproperty

import six

from eventsourcing.domain.model.events import TimestampEntityEvent


class AbstractSnapshop(six.with_metaclass(ABCMeta)):

    @abstractproperty
    def topic(self):
        """
        Path to the class of the snapshotted entity.
        """

    @abstractproperty
    def state(self):
        """
        State of the snapshotted entity.
        """

    @abstractproperty
    def timestamp(self):
        """
        Timestamp of the snapshot.
        """


class Snapshot(TimestampEntityEvent, AbstractSnapshop):

    def __init__(self, entity_id, timestamp, topic, state):
        super(Snapshot, self).__init__(
            entity_id=entity_id,
            timestamp=timestamp,
            topic=topic,
            state=state,
        )

    @property
    def timestamp(self):
        return self.__dict__['timestamp']

    @property
    def topic(self):
        """Path to the class.
        """
        return self.__dict__['topic']

    @property
    def state(self):
        """
        Snapshotted state of the entity.
        """
        return self.__dict__['state']
