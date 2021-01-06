import json
from abc import ABC, abstractmethod
from base64 import b64decode, b64encode
from uuid import UUID

from eventsourcing.application import (
    AbstractNotificationLog,
    LocalNotificationLog,
    Section,
)
from eventsourcing.persistence import Notification


class NotificationLogAPI(ABC):
    @abstractmethod
    def get_log_section(self, section_id: str) -> str:
        pass


class RemoteNotificationLog(AbstractNotificationLog):
    def __init__(self, api: NotificationLogAPI):
        self.api = api

    def __getitem__(self, section_id: str) -> Section:
        body = self.api.get_log_section(section_id)
        section = json.loads(body)
        return Section(  # type: ignore
            section_id=section["section_id"],
            next_id=section["next_id"],
            items=[self.deserialise_item(item) for item in section["items"]],
        )

    def deserialise_item(self, item: dict) -> Notification:
        return Notification(  # type: ignore
            id=item["id"],
            originator_id=UUID(item["originator_id"]),
            originator_version=item["originator_version"],
            topic=item["topic"],
            state=b64decode(item["state"].encode("utf8")),
        )


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
                "items": [self.serialise_item(item) for item in section.items],
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
