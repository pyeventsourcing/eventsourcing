import six
from six import with_metaclass

from eventsourcing.domain.model.events import QualnameABCMeta
from eventsourcing.infrastructure.event_store import EventStore
from eventsourcing.infrastructure.stored_events.transcoders import make_stored_entity_id


def get_log_reader(name, event_store):
    return LogReader(name=name, event_store=event_store)


class LogReader(with_metaclass(QualnameABCMeta)):

    def __init__(self, name, event_store, page_size=50):
        assert isinstance(name, six.string_types)
        self.name = name
        assert isinstance(event_store, EventStore)
        self.event_store = event_store
        assert isinstance(page_size, six.integer_types)
        self.page_size = page_size

    def get_messages(self, after=None, until=None, limit=None, is_ascending=False, page_size=None):
        for event in self.get_events(after, until, limit, is_ascending, page_size):
            yield event.message

    def get_events(self, after=None, until=None, limit=None, is_ascending=False, page_size=None):
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
        return make_stored_entity_id('Logger', self.name)