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


    # def __getitem__(self, pk):
    #     (stored_entity_id, event_id) = pk
    #     return self._by_id[event_id]
    #
    # def __contains__(self, pk):
    #     (stored_entity_id, event_id) = pk
    #     return event_id in self._by_id
    #
    def get_entity_events(self, stored_entity_id, since=None, before=None, limit=None, query_asc=False):
        if stored_entity_id not in self._by_stored_entity_id:
            return []
        else:
            events = []
            count = 0
            stored_events = self._by_stored_entity_id[stored_entity_id]
            if since is None:
                since_timestamp = None
            else:
                since_timestamp = timestamp_from_uuid(since)
            if before is None:
                before_timestamp = None
            else:
                before_timestamp = timestamp_from_uuid(before)
            for event in stored_events:
                event_timestamp = timestamp_from_uuid(event.event_id)
                if since_timestamp:
                    # Exclude if earlier or equal to the 'since' time.
                    if event_timestamp <= since_timestamp:
                        continue
                if before_timestamp:
                    # Exclude if later or equal to the 'before' time.
                    if event_timestamp >= before_timestamp:
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

    # def get_most_recent_event(self, stored_entity_id):
    #     """
    #     :rtype: eventsourcing.infrastructure.stored_events.transcoders.StoredEvent
    #     """
    #     try:
    #         return self._by_stored_entity_id[stored_entity_id][-1]
    #     except KeyError:
    #         return None

    # def get_topic_events(self, event_topic):
    #     return reversed(self._by_topic[event_topic])
