import six

from eventsourcing.domain.model.events import publish
from eventsourcing.domain.model.sequence import Sequence
from eventsourcing.exceptions import EntityVersionNotFound, SequenceFullError
from eventsourcing.infrastructure.eventplayer import EventPlayer
from eventsourcing.infrastructure.transcoding import EntityVersion


def append_item_to_sequence(name, item, event_player, max_size=None):
    assert isinstance(event_player, EventPlayer)
    last_event = event_player.event_store.get_most_recent_event(name)
    next_version = last_event.entity_version + 1
    if max_size and max_size < next_version:
        raise SequenceFullError
    event = Sequence.Appended(
        entity_id=name,
        entity_version=next_version,
        item=item,
    )
    publish(event)


class SequenceReader(object):
    def __init__(self, sequence, event_player):
        assert isinstance(sequence, Sequence), sequence
        assert isinstance(event_player, EventPlayer), event_player
        self.sequence = sequence
        self.event_player = event_player

    def __getitem__(self, item):
        assert isinstance(item, (six.integer_types, slice))
        sequence_len = None
        stored_entity_id = self.event_player.make_stored_entity_id(self.sequence.name)
        if isinstance(item, six.integer_types):
            if item < 0:
                if sequence_len is None:
                    sequence_len = len(self)
                index = sequence_len + item
            else:
                index = item
            try:
                entity_version = self.event_player.event_store.get_entity_version(stored_entity_id, index)
            except EntityVersionNotFound:
                raise IndexError(
                    "Entity version not found for index {} in sequence '{}'".format(item, self.sequence.name))
            assert isinstance(entity_version, EntityVersion)
            event_id = entity_version.event_id
            events = self.event_player.event_store.get_domain_events(stored_entity_id, after=event_id, limit=1)
            events = list(events)
            if len(events) == 0:
                raise IndexError("Entity version not found for index: {}".format(item))
            return events[0].item
        elif isinstance(item, slice):
            assert item.step == None, "Slice step must be 1: {}".format(str(item.step))
            if item.start is None:
                start_index = 0
            elif item.start < 0:
                if sequence_len is None:
                    sequence_len = len(self)
                start_index = sequence_len + item.start
            else:
                start_index = item.start

            if not isinstance(item.stop, six.integer_types):
                limit = None
            elif item.stop < 0:
                if sequence_len is None:
                    sequence_len = len(self)
                limit = sequence_len + item.stop - start_index
            else:
                limit = item.stop - start_index

            if limit is not None and limit <= 0:
                return []

            try:
                if start_index > 0:
                    version = start_index
                else:
                    version = 0
                start_version = self.event_player.event_store.get_entity_version(stored_entity_id, version)
            except EntityVersionNotFound:
                return []
            else:

                start_event_id = start_version.event_id

                events = self.event_player.event_store.get_domain_events(stored_entity_id,
                                                                         after=start_event_id,
                                                                         limit=limit)
                items = [e.item for e in events]
                return items

    def __len__(self):
        event = self.event_player.get_most_recent_event(self.sequence.name)
        return event.entity_version
