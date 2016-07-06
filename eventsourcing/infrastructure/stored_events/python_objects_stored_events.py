from eventsourcing.infrastructure.stored_events.base import StoredEventRepository
from eventsourcing.infrastructure.stored_events.transcoders import StoredEvent
from eventsourcing.utils.time import timestamp_from_uuid


class PythonObjectsStoredEventRepository(StoredEventRepository):

    serialize_without_json = True
    serialize_with_uuid1 = True

    def __init__(self):
        super(PythonObjectsStoredEventRepository, self).__init__()
        self._by_id = {}
        self._by_stored_entity_id = {}

    def append(self, stored_event):
        assert isinstance(stored_event, StoredEvent)
        stored_entity_id = stored_event.stored_entity_id
        event_id = stored_event.event_id

        # Remove entity if it's a discarded event.
        if stored_event.event_topic.endswith('Discarded'):
            self.remove_entity(stored_entity_id)

        # Otherwise add event to entity's list of events.
        else:
            # Index by entity ID.
            if stored_entity_id not in self._by_stored_entity_id:
                self._by_stored_entity_id[stored_entity_id] = []
            self._by_stored_entity_id[stored_entity_id].append(stored_event)

            # Index by event ID.
            self._by_id[event_id] = stored_event

    def remove_entity(self, stored_entity_id):
        if stored_entity_id in self._by_stored_entity_id:
            for stored_event in self._by_stored_entity_id.pop(stored_entity_id):
                del(self._by_id[stored_event.event_id])

    def get_entity_events(self, stored_entity_id, after=None, until=None, limit=None, query_ascending=True,
                          results_ascending=True):
        if stored_entity_id not in self._by_stored_entity_id:
            return []
        else:
            # Get a copy of the list of stored events for this entity.
            stored_events = self._by_stored_entity_id[stored_entity_id][:]

            # Stored event, here, are in ascending order (because they get appended to a list).
            if not query_ascending:
                stored_events.reverse()

            # Get timestamps (floats) from the UUID hex strings (chronologically to compare events).
            if after is None:
                after_timestamp = None
            else:
                after_timestamp = timestamp_from_uuid(after)
            if until is None:
                until_timestamp = None
            else:
                until_timestamp = timestamp_from_uuid(until)

            # Start counting events (needed to stop when limit is reached).
            count = 0

            # Initialise the query results.
            query_results = []

            # Iterate over the stored events, excluding things that don't match.
            for event in stored_events:
                event_timestamp = timestamp_from_uuid(event.event_id)

                if limit is not None and count >= limit:
                    break

                # Exclude if earlier than the 'after' time.
                if after_timestamp:
                    if query_ascending:
                        if event_timestamp <= after_timestamp:
                            continue
                    else:
                        if event_timestamp < after_timestamp:
                            continue

                # Exclude if later than the 'until' time.
                if until_timestamp:
                    if query_ascending:
                        if event_timestamp > until_timestamp:
                            continue
                    else:
                        if event_timestamp >= until_timestamp:
                            continue

                query_results.append(event)
                count += 1

                if results_ascending != query_ascending:
                    query_results.reverse()

            return query_results
