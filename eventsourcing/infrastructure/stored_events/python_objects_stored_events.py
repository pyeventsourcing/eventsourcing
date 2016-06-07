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
        self._by_topic = {}

    def append(self, stored_event):
        assert isinstance(stored_event, StoredEvent)
        event_id = stored_event.event_id
        stored_entity_id = stored_event.stored_entity_id
        topic = stored_event.event_topic

        if topic.endswith('Discarded'):

            self.remove_entity(stored_entity_id)

        else:
            # Index by event ID.
            self._by_id[event_id] = stored_event

            # Index by entity ID.
            if stored_entity_id not in self._by_stored_entity_id:
                self._by_stored_entity_id[stored_entity_id] = []
            self._by_stored_entity_id[stored_entity_id].append(stored_event)

            # Index by event topic.
            if topic not in self._by_topic:
                self._by_topic[topic] = []
            self._by_topic[topic].append(stored_event)

    def remove_entity(self, stored_entity_id):
        if stored_entity_id in self._by_stored_entity_id:
            for stored_event in self._by_stored_entity_id.pop(stored_entity_id):
                del(self._by_id[stored_event.event_id])
                if stored_event.event_topic in self._by_topic:
                    self._by_topic[stored_event.event_topic].remove(stored_event)

    def get_entity_events(self, stored_entity_id, after=None, until=None, limit=None, query_asc=False):
        if stored_entity_id not in self._by_stored_entity_id:
            return []
        else:
            events = []
            count = 0
            stored_events = self._by_stored_entity_id[stored_entity_id]
            if after is None:
                after_timestamp = None
            else:
                after_timestamp = timestamp_from_uuid(after)
            if until is None:
                until_timestamp = None
            else:
                until_timestamp = timestamp_from_uuid(until)
            for event in stored_events:
                event_timestamp = timestamp_from_uuid(event.event_id)
                if after_timestamp:
                    # Exclude if earlier or equal to the 'after' time.
                    if event_timestamp <= after_timestamp:
                        continue
                if until_timestamp:
                    # Exclude if later than the 'until' time.
                    if event_timestamp > until_timestamp:
                        continue
                count += 1
                events.append(event)

            if limit is not None:
                if not query_asc:
                    events.reverse()
                events = events[:min(limit, len(events))]
                if not query_asc:
                    events.reverse()

            return events
