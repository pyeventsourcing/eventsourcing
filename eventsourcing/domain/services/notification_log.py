import six

from eventsourcing.domain.model.notification_log import NotificationLog
from eventsourcing.domain.model.sequence import SequenceRepository
from eventsourcing.domain.services.eventplayer import EventPlayer
from eventsourcing.domain.services.sequence import append_item_to_sequence, SequenceReader

#  Command to append to notificaiton log:

#  - Get current sequence ID from time-bucketed log. Get or create sequence, retry after concurrency error.

#  - If you find the sequence full, then back-off, and increment sequence ID time bucketed log after
#    checking the time-bucketed log hasn't been updated in the meantime. Restart command.

#  - Add item to sequence.

#  - If you fill the sequence, then increment sequence ID time bucketed log.

def append_item_to_notification_log(notification_log, item, sequence_repo):

    assert isinstance(notification_log, NotificationLog), notification_log
    assert isinstance(sequence_repo, SequenceRepository)
    # Get the sequence.
    current_sequence = get_current_notification_log_sequence(notification_log, sequence_repo)
    append_item_to_sequence(current_sequence.name, item, sequence_repo.event_player)


def get_current_notification_log_sequence(notification_log, sequence_repo):
    # Currently just get sequence for log.
    return sequence_repo.get_or_create(notification_log.id, notification_log.sequence_max_size)


class NotificationLogReader(object):
    def __init__(self, notification_log, event_player, sequence_repo):
        assert isinstance(notification_log, NotificationLog), notification_log
        assert isinstance(event_player, EventPlayer), event_player
        assert isinstance(sequence_repo, SequenceRepository)
        self.notification_log = notification_log
        self.event_player = event_player
        self.sequence_repo = sequence_repo

    def __getitem__(self, item):
        assert isinstance(item, (six.integer_types, slice))
        # Todo: Change this to read the current sequence ID from a timebucketed log.
        sequence = get_current_notification_log_sequence(self.notification_log, self.sequence_repo)
        reader = SequenceReader(sequence, self.sequence_repo.event_player)
        return reader[item]


    # def __len__(self):
    #     event = self.event_player.get_most_recent_event(self.sequence.name)
    #     return event.entity_version
