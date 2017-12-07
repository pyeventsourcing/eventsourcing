# import itertools
# from collections import defaultdict
#
# from eventsourcing.exceptions import ConcurrencyError, DatasourceOperationError
# from eventsourcing.infrastructure.eventstore import AbstractStoredEventRepository
# from eventsourcing.infrastructure.transcoding import EntityVersion
# from eventsourcing.utils.times import timestamp_from_uuid
#
#
# class PythonObjectsStoredEventRepository(AbstractStoredEventRepository):
#     def __init__(self, *args, **kwargs):
#         super(PythonObjectsStoredEventRepository, self).__init__(*args, **kwargs)
#         self._by_id = {}
#         self._by_stored_entity_id = {}
#         self._originator_versions = defaultdict(lambda: defaultdict(lambda: itertools.chain([0], itertools.cycle([
# 1]))))
#         self._event_id_by_originator_version_id = {}
#
#     def write_version_and_event(self, new_stored_event, new_version_number=None, max_retries=3,
#                                 artificial_failure_rate=0):
#
#         if artificial_failure_rate:
#             raise DatasourceOperationError('Artificial failure')
#
#         # Put the event in the various dicts.
#         stored_entity_id = new_stored_event.entity_id
#         if self.always_write_originator_version and new_version_number is not None:
#             versions = self._originator_versions[stored_entity_id]
#             if next(versions[new_version_number]) != 0:
#                 raise ConcurrencyError("New version {} for entity {} already exists"
#                                        "".format(new_version_number, stored_entity_id))
#             originator_version_id = self.make_originator_version_id(stored_entity_id, new_version_number)
#             self._event_id_by_originator_version_id[originator_version_id] = new_stored_event.event_id
#
#         # Remove entity if it's a discarded event.
#         if new_stored_event.event_topic.endswith('Discarded'):
#             self.remove_entity(stored_entity_id)
#
#         # Otherwise add event to entity's list of events.
#         else:
#             # Index by entity ID.
#             if stored_entity_id not in self._by_stored_entity_id:
#                 self._by_stored_entity_id[stored_entity_id] = []
#             self._by_stored_entity_id[stored_entity_id].append(new_stored_event)
#
#             # Index by event ID.
#             self._by_id[new_stored_event.event_id] = new_stored_event
#
#     def get_originator_version(self, stored_entity_id, version_number):
#         versions = self._originator_versions[stored_entity_id]
#         if version_number not in versions:
#             self.raise_originator_version_not_found(stored_entity_id, version_number)
#         originator_version_id = self.make_originator_version_id(stored_entity_id, version_number)
#         return EntityVersion(
#             originator_version_id=originator_version_id,
#             event_id=self._event_id_by_originator_version_id[originator_version_id]
#         )
#
#     def remove_entity(self, stored_entity_id):
#         if stored_entity_id in self._by_stored_entity_id:
#             for stored_event in self._by_stored_entity_id.pop(stored_entity_id):
#                 del (self._by_id[stored_event.event_id])
#         if self.always_write_originator_version:
#             del (self._originator_versions[stored_entity_id])
#
#     def get_stored_events(self, stored_entity_id, after=None, until=None, limit=None, query_ascending=True,
#                           results_ascending=True, include_after_when_ascending=False,
#                           include_until_when_descending=False):
#
#         assert limit is None or limit >= 1, limit
#
#         if stored_entity_id not in self._by_stored_entity_id:
#             return []
#         else:
#             # Get a copy of the list of stored events for this entity.
#             stored_events = self._by_stored_entity_id[stored_entity_id][:]
#
#             # Stored event, here, are in ascending order (because they get appended to a list).
#             if not query_ascending:
#                 stored_events.reverse()
#
#             # Get timestamps (floats) from the UUID hex strings (chronologically to compare events).
#             if after is None:
#                 after_timestamp = None
#             else:
#                 after_timestamp = timestamp_from_uuid(after)
#             if until is None:
#                 until_timestamp = None
#             else:
#                 until_timestamp = timestamp_from_uuid(until)
#
#             # Start counting events (needed to stop when limit is reached).
#             count = 0
#
#             # Initialise the query results.
#             query_results = []
#
#             # Iterate over the stored events, excluding things that don't match.
#             for event in stored_events:
#                 event_timestamp = timestamp_from_uuid(event.event_id)
#
#                 if limit is not None and count >= limit:
#                     break
#
#                 # Exclude if earlier than the 'after' time.
#                 if after_timestamp:
#                     if query_ascending and not include_after_when_ascending:
#                         if event_timestamp <= after_timestamp:
#                             continue
#                     else:
#                         if event_timestamp < after_timestamp:
#                             continue
#
#                 # Exclude if later than the 'until' time.
#                 if until_timestamp:
#                     if query_ascending or include_until_when_descending:
#                         if event_timestamp > until_timestamp:
#                             continue
#                     else:
#                         if event_timestamp >= until_timestamp:
#                             continue
#
#                 query_results.append(event)
#                 count += 1
#
#                 if results_ascending != query_ascending:
#                     query_results.reverse()
#
#             return query_results
