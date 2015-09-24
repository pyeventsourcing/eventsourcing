from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.infrastructure.stored_events.base import StoredEventRepository, serialize_domain_event, \
    recreate_domain_event


class EventStore(object):

    def __init__(self, stored_event_repo):
        assert isinstance(stored_event_repo, StoredEventRepository)
        self.stored_event_repo = stored_event_repo

    def append(self, domain_event):
        assert isinstance(domain_event, DomainEvent)

        # Serialize the domain event.
        stored_event = serialize_domain_event(domain_event)

        # Append the stored event to the stored event repo.
        self.stored_event_repo.append(stored_event)

    def get_entity_events(self, stored_entity_id):

        # Get all the stored events for the entity.
        stored_events = self.stored_event_repo.get_entity_events(stored_entity_id=stored_entity_id)

        # Recreate the entity's domain events from the stored events.
        return map(recreate_domain_event, stored_events)
