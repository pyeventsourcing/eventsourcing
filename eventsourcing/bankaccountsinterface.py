import json
from abc import ABC, abstractmethod
from typing import Generic
from uuid import UUID

from eventsourcing.application import TApplication
from eventsourcing.notificationlogview import (
    AbstractNotificationLogView,
    JSONNotificationLogView,
)
from eventsourcing.remotenotificationlog import (
    NotificationLogAPI,
    RemoteNotificationLog,
)
from eventsourcing.test_application import BankAccounts


class ApplicationAdapter(ABC, Generic[TApplication]):
    def __init__(self, app: TApplication):
        self.app = app
        self.log = self.construct_log_view()

    @abstractmethod
    def construct_log_view(
        self,
    ) -> AbstractNotificationLogView:
        pass


class BankAccountsAPI(NotificationLogAPI):
    @abstractmethod
    def open_account(self, body: str) -> str:
        pass


class BankAccountsJSONAPI(
    BankAccountsAPI,
    ApplicationAdapter[BankAccounts],
):
    def construct_log_view(self):
        return JSONNotificationLogView(self.app.log)

    def get_log_section(self, section_id: str) -> str:
        return self.log.get(section_id)

    def open_account(self, request: str) -> str:
        kwargs = json.loads(request)
        account_id = self.app.open_account(**kwargs)
        return json.dumps({"account_id": account_id.hex})


class BankAccountsJSONClient:
    def __init__(self, api: BankAccountsAPI):
        self.api = api
        self.log = RemoteNotificationLog(api)

    def open_account(
        self, full_name, email_address
    ) -> UUID:
        body = json.dumps(
            {
                "full_name": full_name,
                "email_address": email_address,
            }
        )
        body = self.api.open_account(body)
        return UUID(json.loads(body)["account_id"])
