import six

from eventsourcing.infrastructure.stored_events.base import StoredEventRepository


class EventStore(object):

    def __init__(self, stored_event_repo):
        assert isinstance(stored_event_repo, StoredEventRepository), stored_event_repo
        self.stored_event_repo = stored_event_repo

    def append(self, domain_event):
        # Serialize the domain event.
        stored_event = self.stored_event_repo.serialize(domain_event)

        # Append the stored event to the stored event repo.
        self.stored_event_repo.append(stored_event)

    def get_entity_events(self, stored_entity_id, after=None, until=None, limit=None, page_size=None):
        # Get the events that have been stored for the entity.
        if not page_size:
            stored_events = self.stored_event_repo.get_entity_events(
                stored_entity_id=stored_entity_id,
                after=after,
                until=until,
                limit=limit
            )
        else:
            stored_events = self.stored_event_repo.iterate_entity_events(
                stored_entity_id=stored_entity_id,
                after=after,
                until=until,
                limit=limit,
                page_size=page_size
            )

        # Deserialize all the stored event objects into domain event objects.
        return six.moves.map(self.stored_event_repo.deserialize, stored_events)

    def get_most_recent_event(self, stored_entity_id, until=None):
        """Returns last event for given entity ID.

        :rtype: DomainEvent, NoneType
        """
        stored_event = self.stored_event_repo.get_most_recent_event(stored_entity_id, until=until)
        return None if stored_event is None else self.stored_event_repo.deserialize(stored_event)
