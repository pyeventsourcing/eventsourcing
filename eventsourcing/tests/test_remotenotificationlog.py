import json
import threading
from abc import ABC, abstractmethod
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread
from typing import Callable, Generic, List
from unittest.case import TestCase
from uuid import UUID

from eventsourcing.application import TApplication
from eventsourcing.interface import (
    AbstractNotificationLogView,
    JSONNotificationLogView,
    NotificationLogAPI,
    RemoteNotificationLog,
)
from eventsourcing.tests.test_application import BankAccounts


class TestRemoteNotificationLog(TestCase):
    def test_directly(self):
        client = BankAccountsJSONClient(BankAccountsJSONAPI(BankAccounts()))
        account_id1 = client.open_account("Alice", "alice@example.com")
        account_id2 = client.open_account("Bob", "bob@example.com")

        # Get the "first" section of log.
        section = client.log["1,10"]
        self.assertEqual(len(section.items), 2)
        self.assertEqual(section.items[0].originator_id, account_id1)
        self.assertEqual(section.items[1].originator_id, account_id2)

    def test_with_http(self):
        server_address = ("127.0.0.1", 8080)

        server = HTTPApplicationServer(
            address=server_address,
            handler=BankAccountsHTTPHandler,
        )
        server.start()
        if not server.is_running.wait(timeout=5):
            server.stop()
            self.fail("Unable to start HTTPApplicationServer")

        try:
            client = BankAccountsJSONClient(
                BankAccountsHTTPClient(server_address=server_address)
            )

            account_id1 = client.open_account("Alice", "alice@example.com")
            account_id2 = client.open_account("Bob", "bob@example.com")

            # Get the "first" section of log.
            section = client.log["1,10"]
            self.assertEqual(len(section.items), 2)
            self.assertEqual(section.items[0].originator_id, account_id1)
            self.assertEqual(section.items[1].originator_id, account_id2)
        finally:
            server.stop()

    def test_with_http_and_threads(self):
        server_address = ("127.0.0.1", 8081)

        server = HTTPApplicationServer(
            address=server_address,
            handler=BankAccountsHTTPHandler,
        )
        server.start()
        if not server.is_running.wait(timeout=5):
            server.stop()
            self.fail("Unable to start HTTPApplicationServer")

        try:
            self.has_errors = False

            def open_account():
                client = BankAccountsJSONClient(
                    BankAccountsHTTPClient(server_address=server_address)
                )
                for _ in range(30):
                    try:
                        client.open_account("Alice", "alice@example.com")
                        # print(threading.get_ident(), account_id1)
                    except Exception as e:
                        print(threading.get_ident(), "error:", e)
                        self.has_errors = True
                        raise

            thread1 = Thread(target=open_account)
            thread1.start()
            thread2 = Thread(target=open_account)
            thread2.start()

            thread1.join()
            thread2.join()

            self.assertFalse(self.has_errors)

            # Check the notification log.
            client = BankAccountsJSONClient(
                BankAccountsHTTPClient(server_address=server_address)
            )
            self.assertEqual(len(client.log["1,10"].items), 10)
            self.assertEqual(len(client.log["11,20"].items), 10)
            self.assertEqual(len(client.log["21,30"].items), 10)
            self.assertEqual(len(client.log["31,40"].items), 10)
            self.assertEqual(len(client.log["41,50"].items), 10)
            self.assertEqual(len(client.log["51,60"].items), 10)
            self.assertEqual(len(client.log["61,70"].items), 0)

        finally:
            server.stop()


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

    def open_account(self, full_name, email_address) -> UUID:
        body = json.dumps(
            {
                "full_name": full_name,
                "email_address": email_address,
            }
        )
        body = self.api.open_account(body)
        return UUID(json.loads(body)["account_id"])


class HTTPApplicationServer(Thread):
    prepare: List[Callable] = []

    def __init__(self, address, handler):
        super(HTTPApplicationServer, self).__init__(daemon=True)
        self.server = HTTPServer(
            server_address=address,
            RequestHandlerClass=handler,
        )
        self.is_running = Event()

    def run(self):
        [f() for f in self.prepare]
        self.is_running.set()
        self.server.serve_forever()

    def stop(self):
        self.server.shutdown()
        self.join()

    @classmethod
    def before_first_request(cls, f):
        HTTPApplicationServer.prepare.append(f)
        return f


class BankAccountsHTTPHandler(BaseHTTPRequestHandler):
    def do_PUT(self):
        if self.path.startswith("/accounts/"):
            length = int(self.headers["Content-Length"])
            request_msg = self.rfile.read(length).decode("utf8")
            body = adapter.open_account(request_msg)
            status = 201
        else:
            body = "Not found: " + self.path
            status = 404
        self.send(body, status)

    def do_GET(self):
        if self.path.startswith("/notifications/"):
            section_id = self.path.split("/")[-1]
            body = adapter.get_log_section(section_id)
            status = 200
        else:
            body = "Not found: " + self.path
            status = 404
        self.send(body, status)

    def send(self, body: str, status: int):
        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode("utf8"))


class BankAccountsHTTPClient(BankAccountsAPI):
    def __init__(self, server_address):
        self.connection = HTTPConnection(*server_address)

    def get_log_section(self, section_id: str) -> str:
        return self.request("GET", "/notifications/{}".format(section_id))

    def open_account(self, body: str) -> str:
        return self.request("PUT", "/accounts/", body.encode("utf8"))

    def request(self, method, url, body=None):
        self.connection.request(method, url, body)
        return self.get_response()

    def get_response(self):
        response = self.connection.getresponse()
        return response.read().decode()


adapter: BankAccountsAPI


@HTTPApplicationServer.before_first_request
def init_bank_accounts() -> None:
    global adapter
    adapter = BankAccountsJSONAPI(BankAccounts())
