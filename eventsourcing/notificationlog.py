from abc import ABC, abstractmethod
from typing import List, Optional

from eventsourcing.domain import ImmutableObject
from eventsourcing.notification import Notification
from eventsourcing.recorders import ApplicationRecorder


def format_section_id(first, limit):
    return "{},{}".format(first, limit)


class Section(ImmutableObject):
    section_id: str
    items: List[Notification]
    next_id: Optional[str]


USE_REGULAR_SECTIONS = True


class AbstractNotificationLog(ABC):
    @abstractmethod
    def __getitem__(self, section_id: str) -> Section:
        """
        Returns section of notification log.
        """


class LocalNotificationLog(AbstractNotificationLog):
    DEFAULT_SECTION_SIZE = 10

    def __init__(
        self,
        recorder: ApplicationRecorder,
        section_size: int = DEFAULT_SECTION_SIZE,
    ):
        self.recorder = recorder
        self.section_size = section_size

    def __getitem__(self, section_id: str) -> Section:
        # Interpret the section ID.
        parts = section_id.split(",")
        part1 = int(parts[0])
        part2 = int(parts[1])
        start = max(1, part1)
        limit = min(
            max(0, part2 - start + 1), self.section_size
        )

        # Select notifications.
        notifications = self.recorder.select_notifications(
            start, limit
        )

        # Get next section ID.
        if len(notifications):
            last_id = notifications[-1].id
            return_id = format_section_id(
                notifications[0].id, last_id
            )
            if len(notifications) == limit:
                next_start = last_id + 1
                next_id = format_section_id(
                    next_start, next_start + limit - 1
                )
            else:
                next_id = None
        else:
            return_id = None
            next_id = None

        # Return a section of the notification log.
        return Section(  # type: ignore
            section_id=return_id,
            items=notifications,
            next_id=next_id,
        )
