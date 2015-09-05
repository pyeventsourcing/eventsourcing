from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.infrastructure.stored_events.base import StoredEventRepository, serialize_domain_event


class EventStore(object):

    def __init__(self, stored_event_repo):
        assert isinstance(stored_event_repo, StoredEventRepository)
        self.stored_event_repo = stored_event_repo

    def append(self, domain_event):
        assert isinstance(domain_event, DomainEvent)
        stored_event = serialize_domain_event(domain_event)
        self.stored_event_repo.append(stored_event)
