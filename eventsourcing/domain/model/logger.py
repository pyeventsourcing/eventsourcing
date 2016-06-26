import six
from six import with_metaclass

from eventsourcing.domain.model.events import DomainEvent, publish, QualnameABCMeta


def get_logger(name):
    """
    :rtype: Logger
    """
    return Logger(name=name)


class Logger(with_metaclass(QualnameABCMeta)):

    class MessageLogged(DomainEvent):
        @property
        def message(self):
            return self.__dict__['message']

    def __init__(self, name):
        assert isinstance(name, six.string_types)
        self.name = name

    def append(self, message):
        assert isinstance(message, six.string_types)
        event = Logger.MessageLogged(
            entity_id=self.name,
            entity_version=0,
            message=message,
        )
        publish(event)
        return event
