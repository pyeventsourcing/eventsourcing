from abc import ABCMeta, abstractproperty

import six

from eventsourcing.domain.model.events import EventWithOriginatorVersion, EventWithTimestamp, EventWithOriginatorID


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
    def originator_id(self):
        """
        ID of the snapshotted entity.
        """

    @abstractproperty
    def originator_version(self):
        """
        Version of the last event applied to the entity.
        """


class Snapshot(EventWithTimestamp, EventWithOriginatorVersion, EventWithOriginatorID, AbstractSnapshop):
    def __init__(self, originator_id, originator_version, topic, state):
        super(Snapshot, self).__init__(
            originator_id=originator_id,
            originator_version=originator_version,
            topic=topic,
            state=state,
        )

    @property
    def topic(self):
        """
        Path to the class of the snapshotted entity.
        """
        return self.__dict__['topic']

    @property
    def state(self):
        """
        State of the snapshotted entity.
        """
        return self.__dict__['state']
