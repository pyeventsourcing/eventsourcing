import six
from six import with_metaclass

from eventsourcing.domain.model.events import DomainEvent, publish, QualnameABCMeta
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.transcoders import make_stored_entity_id


def get_log(name, event_store):
    return Log(name=name, event_store=event_store)


class Log(with_metaclass(QualnameABCMeta)):

    class MessageLogged(DomainEvent):
        pass

    def __init__(self, name, event_store, page_size=50):
        assert isinstance(event_store, EventStore)
        self.name = name
        self.event_store = event_store
        self.page_size = page_size

    def append(self, message):
        assert isinstance(message, six.string_types)
        event = Log.MessageLogged(entity_id=self.name, entity_version=0, message=message)
        publish(event)
        return event

    def get_lines(self, after=None, until=None, limit=None, is_ascending=False, page_size=None):
        for message_logged_event in self.get_message_logged_events(after, until, limit, is_ascending, page_size):
            yield message_logged_event.message

    def get_message_logged_events(self, after=None, until=None, limit=None, is_ascending=False, page_size=None):
        stored_log_id = self.make_stored_log_id()
        for message_logged_event in self.event_store.get_entity_events(
                stored_entity_id=stored_log_id,
                after=after,
                until=until,
                limit=limit,
                is_ascending=is_ascending,
                page_size=page_size,
        ):
            yield message_logged_event

    def make_stored_log_id(self):
        return make_stored_entity_id('Log', self.name)
