import json
from abc import ABC, abstractmethod
from base64 import b64encode

from eventsourcing.persistence import Notification
from eventsourcing.application import LocalNotificationLog


class AbstractNotificationLogView(ABC):
    """
    Presents serialised notification log sections.
    """

    def __init__(self, log: LocalNotificationLog):
        self.log = log

    @abstractmethod
    def get(self, section_id: str) -> str:
        """Returns notification log section"""


class JSONNotificationLogView(AbstractNotificationLogView):
    """
    Presents notification log sections in JSON format.
    """

    def get(self, section_id: str) -> str:
        section = self.log[section_id]
        return json.dumps(
            {
                "section_id": section.section_id,
                "next_id": section.next_id,
                "items": [
                    self.serialise_item(item)
                    for item in section.items
                ],
            }
        )

    def serialise_item(self, item: Notification) -> dict:
        return {
            "id": item.id,
            "originator_id": item.originator_id.hex,
            "originator_version": item.originator_version,
            "topic": item.topic,
            "state": b64encode(item.state).decode("utf8"),
        }
