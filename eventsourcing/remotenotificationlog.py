import json
from abc import ABC, abstractmethod
from base64 import b64decode
from uuid import UUID

from eventsourcing.persistence import Notification
from eventsourcing.application import AbstractNotificationLog, Section


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
            items=[
                self.deserialise_item(item)
                for item in section["items"]
            ],
        )

    def deserialise_item(self, item: dict) -> Notification:
        return Notification(  # type: ignore
            id=item["id"],
            originator_id=UUID(item["originator_id"]),
            originator_version=item["originator_version"],
            topic=item["topic"],
            state=b64decode(item["state"].encode("utf8")),
        )
