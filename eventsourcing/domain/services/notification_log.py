import six

from eventsourcing.domain.model.log import LogRepository
from eventsourcing.domain.model.notification_log import NotificationLog
from eventsourcing.domain.model.sequence import SequenceRepository, Sequence
from eventsourcing.domain.services.eventstore import AbstractEventStore
from eventsourcing.domain.services.sequence import append_item_to_sequence, SequenceReader

# Todo: Retries after concurrency error.
# Todo: If current sequence is full at start of append, it shouldn't be because
# it should have been rolled over, so back-off, and increment sequence ID time
# bucketed log after checking the time-bucketed log hasn't been updated in the
# meantime. Restart command.

from eventsourcing.exceptions import SequenceFullError
from eventsourcing.infrastructure.log_reader import LogReader


def append_item_to_notification_log(notification_log, item, sequence_repo, log_repo, sequence_event_player):
    assert isinstance(notification_log, NotificationLog), notification_log
    assert isinstance(sequence_repo, SequenceRepository)
    assert isinstance(log_repo, LogRepository)
    # Get the sequence.
    current_sequence = get_current_notification_log_sequence(notification_log, sequence_repo, log_repo, sequence_event_player)
    assert isinstance(current_sequence, Sequence)
    try:
        append_item_to_sequence(current_sequence.name, item, sequence_repo.event_player, notification_log.sequence_size)
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
    assert isinstance(log_repo, LogRepository), log_repo
    log = log_repo.get_or_create(notification_log.name, notification_log.bucket_size)
    log_reader = LogReader(log, event_store)
    events = list(log_reader.get_events(limit=1))
    if len(events):
        most_recent_event = events[0]
        sequence_id = most_recent_event.message
    else:
        sequence_id = make_notification_log_sequence_id(notification_log.name, 0)
    return sequence_id


def make_notification_log_sequence_id(notification_log_name, sequence_number):
    return '{}::{}'.format(notification_log_name, sequence_number)


class NotificationLogReader(object):
    def __init__(self, notification_log, sequence_repo, log_repo, event_store):
        assert isinstance(notification_log, NotificationLog), notification_log
        assert isinstance(sequence_repo, SequenceRepository)
        assert isinstance(log_repo, LogRepository)
        assert isinstance(event_store, AbstractEventStore), event_store
        self.notification_log = notification_log
        self.sequence_repo = sequence_repo
        self.log_repo = log_repo
        self.event_store = event_store

    def __getitem__(self, item):
        assert isinstance(item, (six.integer_types, slice))
        if isinstance(item, six.integer_types):
            if item < 0:
                raise IndexError('Negative index values not supported by notification log')
            sequence_number, sequence_item = divmod(item, self.notification_log.sequence_size)
        elif isinstance(item, slice):
            if isinstance(item.start, six.integer_types):
                if item.start < 0:
                    raise IndexError('Negative index values not supported by notification log')
                sequence_number, sequence_slice_start = divmod(item.start, self.notification_log.sequence_size)
            else:
                sequence_number, sequence_slice_start = 0, 0

            # Todo: Read from subsequent sequences if slice.stop goes beyond the end of the sequence.
            # Naively assumes item.stop is within the sequence.
            sequence_item = slice(sequence_slice_start, item.stop)

        sequence_id = make_notification_log_sequence_id(self.notification_log.name, sequence_number)
        sequence = self.sequence_repo.get_or_create(sequence_id)

        reader = SequenceReader(sequence, self.sequence_repo.event_player)
        try:
            return reader[sequence_item]
        except IndexError:
            msg = "Notification log item {} not found (item {} in sequence {})".format(item, sequence_item, sequence_number)
            raise IndexError(msg)

    def __len__(self):
        # Get the sequence.
        current_sequence = get_current_notification_log_sequence(self.notification_log, self.sequence_repo, self.log_repo,
                                                                 self.event_store)
        sequence_number = int(current_sequence.name.split('::')[-1])
        event = self.sequence_repo.event_player.get_most_recent_event(current_sequence.name)
        sequence_count = event.entity_version
        return (sequence_number * self.notification_log.sequence_size) + sequence_count
