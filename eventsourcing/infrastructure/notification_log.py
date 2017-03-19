import six

from eventsourcing.domain.model.timebucketedlog import TimebucketedlogRepository
from eventsourcing.domain.model.notificationlog import NotificationLog
from eventsourcing.domain.model.sequence import Sequence, SequenceRepository
from eventsourcing.exceptions import SequenceFullError
from eventsourcing.infrastructure.eventstore import AbstractEventStore
from eventsourcing.infrastructure.timebucketedlog_reader import TimebucketedlogReader
from eventsourcing.infrastructure.sequence import SequenceReader, append_item_to_sequence


def append_item_to_notification_log(notification_log, item, sequence_repo, log_repo, event_store):
    """Appends item to current sequence, unless the sequence is full.

    If the sequence is full, the sequence number is incremented and
    the item is added to the next sequence."""
    assert isinstance(notification_log, NotificationLog), notification_log
    assert isinstance(sequence_repo, SequenceRepository)
    assert isinstance(log_repo, TimebucketedlogRepository)
    # Get the sequence.
    current_sequence = get_current_notification_log_sequence(notification_log, sequence_repo, log_repo, event_store)
    assert isinstance(current_sequence, Sequence)
    try:
        append_item_to_sequence(current_sequence.name, item, sequence_repo.event_player,
                                notification_log.sequence_size)
    except SequenceFullError:
        # Roll over the sequence.
        # - construct next sequence ID
        current_sequence_number = int(current_sequence.name.split('::')[-1])
        next_sequence_id = make_notification_log_sequence_id(notification_log.name, current_sequence_number + 1)
        # - write message into time-bucketed log
        log = log_repo.get_or_create(notification_log.name, notification_log.bucket_size)
        log.append_message(next_sequence_id)
        next_sequence = sequence_repo.get_or_create(next_sequence_id)

        append_item_to_sequence(next_sequence.name, item, sequence_repo.event_player, notification_log.sequence_size)


def get_current_notification_log_sequence(notification_log, sequence_repo, log_repo, event_store):
    # Get time-bucketed log.
    sequence_id = get_current_notification_log_sequence_id(notification_log, sequence_repo, log_repo, event_store)
    return sequence_repo.get_or_create(sequence_id)


def get_current_notification_log_sequence_id(notification_log, sequence_repo, log_repo, event_store):
    assert isinstance(notification_log, NotificationLog), notification_log
    assert isinstance(sequence_repo, SequenceRepository), sequence_repo
    assert isinstance(log_repo, TimebucketedlogRepository), log_repo
    log = log_repo.get_or_create(notification_log.name, notification_log.bucket_size)
    log_reader = TimebucketedlogReader(log, event_store)
    events = list(log_reader.get_events(limit=1))
    if len(events):
        most_recent_event = events[0]
        sequence_id = most_recent_event.message
    else:
        sequence_id = make_notification_log_sequence_id(notification_log.name, 0)
    return sequence_id


def make_notification_log_sequence_id(notification_log_name, sequence_number):
    assert isinstance(notification_log_name, six.string_types)
    assert isinstance(sequence_number, six.integer_types)
    return '{}::{}'.format(notification_log_name, sequence_number)


class NotificationLogReader(object):
    def __init__(self, notification_log, sequence_repo, log_repo, event_store):
        assert isinstance(notification_log, NotificationLog), notification_log
        assert isinstance(sequence_repo, SequenceRepository)
        assert isinstance(log_repo, TimebucketedlogRepository)
        assert isinstance(event_store, AbstractEventStore), event_store
        self.notification_log = notification_log
        self.sequence_repo = sequence_repo
        self.log_repo = log_repo
        self.event_store = event_store

    def __getitem__(self, item):
        assert isinstance(item, (six.integer_types, slice))
        sequence_size = self.notification_log.sequence_size
        sequence_number = None
        sequence_item = None

        if isinstance(item, six.integer_types):
            # Get a single item from a sequence.
            if item < 0:
                raise IndexError('Negative index values not yet supported by notification log')
            sequence_number, sequence_item = divmod(item, sequence_size)
        elif isinstance(item, slice):
            # Get a number of items from part of a sequence.
            if item.start is None or item.stop is None:
                raise IndexError('Slices without both start and stop values are not supported')
            if item.start < 0 or item.stop < 0:
                raise IndexError('Negative index values not yet supported by notification log')
            if item.step is not None:
                raise IndexError('Slices with a step value are not supported')

            # Identify sequence numbers and sequence index values from start and stop.
            start_sequence_number, slice_start = divmod(item.start, sequence_size)
            stop_sequence_number = (item.stop - 1) // sequence_size

            # Check everything will come from a single sequence.
            if start_sequence_number != stop_sequence_number:
                raise IndexError("Slice crosses sequence objects ({}, {}), which isn't supported yet".format(
                    start_sequence_number, stop_sequence_number
                ))

            # Remember the sequence number.
            sequence_number = start_sequence_number

            # Calculate sequence slice stop value.
            index_offset = sequence_number * sequence_size
            slice_stop = item.stop - index_offset
            sequence_item = slice(slice_start, slice_stop)

        # Make a sequence ID from the notification log name and the sequence number.
        sequence_id = make_notification_log_sequence_id(self.notification_log.name, sequence_number)

        # Read item(s) from the sequence.
        sequence = self.sequence_repo.get_or_create(sequence_id)
        reader = SequenceReader(sequence, self.sequence_repo.event_player)
        try:
            return reader[sequence_item]
        except IndexError:
            msg = "Notification log item {} not found (item {} in sequence {})".format(item, sequence_item,
                                                                                       sequence_number)
            raise IndexError(msg)

    def __len__(self):
        # Get the current sequence.
        current_sequence = get_current_notification_log_sequence(self.notification_log,
                                                                 self.sequence_repo,
                                                                 self.log_repo,
                                                                 self.event_store)
        assert isinstance(current_sequence, Sequence)
        sequence_number = int(current_sequence.name.split('::')[-1])
        event = self.sequence_repo.event_player.get_most_recent_event(current_sequence.name)
        sequence_count = event.entity_version
        return (sequence_number * self.notification_log.sequence_size) + sequence_count
