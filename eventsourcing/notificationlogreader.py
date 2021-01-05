from typing import Iterable

from eventsourcing.persistence import Notification
from eventsourcing.application import AbstractNotificationLog, Section


class NotificationLogReader:
    DEFAULT_SECTION_SIZE = 10

    def __init__(
        self,
        notification_log: AbstractNotificationLog,
        section_size: int = DEFAULT_SECTION_SIZE,
    ):
        self.notification_log = notification_log
        self.section_size = section_size

    def read(
        self, *, start: int
    ) -> Iterable[Notification]:
        section_id = "{},{}".format(
            start, start + self.section_size - 1
        )
        while True:
            section: Section = self.notification_log[
                section_id
            ]
            for item in section.items:
                # Todo: Reintroduce if supporting
                #  sections with regular alignment?
                # if item.id < start:
                #     continue
                yield item
            if section.next_id is None:
                break
            else:
                section_id = section.next_id
