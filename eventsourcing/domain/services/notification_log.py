from eventsourcing.domain.model.notification_log import NotificationLog
from eventsourcing.domain.model.sequence import SequenceRepository
from eventsourcing.domain.services.sequence import append_item_to_sequence


def append_item_to_notification_log(notification_log, item, sequence_repo):
    assert isinstance(notification_log, NotificationLog), notification_log
    assert isinstance(sequence_repo, SequenceRepository)
    current_sequence = sequence_repo[notification_log.id]
    append_item_to_sequence(current_sequence.name, item, sequence_repo.event_player)
