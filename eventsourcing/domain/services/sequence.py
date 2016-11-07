import six

from eventsourcing.domain.model.events import publish
from eventsourcing.domain.model.sequence import Sequence
from eventsourcing.domain.services.eventplayer import EventPlayer
from eventsourcing.domain.services.transcoding import EntityVersion
from eventsourcing.exceptions import EntityVersionDoesNotExist


def append_item_to_sequence(name, item, event_player):
    assert isinstance(event_player, EventPlayer)
    stored_entity_id = event_player.make_stored_entity_id(name)
    last_event = event_player.event_store.get_most_recent_event(stored_entity_id)
    next_version = last_event.entity_version + 1
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
        stored_entity_id = self.event_player.make_stored_entity_id(self.sequence.name)
        if isinstance(item, six.integer_types):
            if item < 0:
                raise IndexError('Negative indexes are not supported')
            try:
                entity_version = self.event_player.event_store.get_entity_version(stored_entity_id, item)
            except EntityVersionDoesNotExist:
                raise IndexError("Entity version not found for index: {}".format(item))
            assert isinstance(entity_version, EntityVersion)
            event_id = entity_version.event_id
            events = self.event_player.event_store.get_entity_events(stored_entity_id, after=event_id, limit=1)
            events = list(events)
            if len(events) == 0:
                raise IndexError("Entity version not found for index: {}".format(item))
            return events[0].item
        elif isinstance(item, slice):
            assert item.step == None, "Slice step must be 1: {}".format(str(item.step))
            if item.start is None:
                start_index = 0
            elif item.start < 0:
                raise IndexError('Negative indexes are not supported')
            else:
                start_index = item.start

            if item.stop is None:
                limit = None
            elif item.stop < 0:
                raise IndexError('Negative indexes are not supported: {}'.format(item.stop))
            else:
                limit = item.stop - item.start

            start_version = self.event_player.event_store.get_entity_version(stored_entity_id, start_index)
            start_event_id = start_version.event_id

            events = self.event_player.event_store.get_entity_events(stored_entity_id,
                                                                                  after=start_event_id,
                                                                                  limit=limit)
            items = [e.item for e in events]
            return items

    def __len__(self):
        event = self.event_player.get_most_recent_event(self.sequence.name)
        return event.entity_version
