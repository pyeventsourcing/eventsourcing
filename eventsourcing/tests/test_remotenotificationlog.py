import json
import threading
from abc import abstractmethod
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread
from typing import Callable, List
from unittest.case import TestCase
from uuid import UUID

from eventsourcing.interface import (
    NotificationLogInterface,
    NotificationLogJSONClient,
    NotificationLogJSONService,
)
from eventsourcing.tests.test_application_with_popo import BankAccounts


class TestRemoteNotificationLog(TestCase):
    def test_directly(self):
        client = BankAccountsJSONClient(BankAccountsJSONService(BankAccounts()))
        account_id1 = client.open_account("Alice", "alice@example.com")
        account_id2 = client.open_account("Bob", "bob@example.com")

        # Get the "first" section of log.
        section = client.log["1,10"]
        self.assertEqual(len(section.items), 2)
        self.assertEqual(section.items[0].originator_id, account_id1)
        self.assertEqual(section.items[1].originator_id, account_id2)

        # Get notifications start 1, limit 10.
        notifications = client.log.select(start=1, limit=10)
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0].originator_id, account_id1)
        self.assertEqual(notifications[1].originator_id, account_id2)

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

            # Get notifications start 1, limit 10.
            notifications = client.log.select(1, 10)
            self.assertEqual(len(notifications), 2)
            self.assertEqual(notifications[0].originator_id, account_id1)
            self.assertEqual(notifications[1].originator_id, account_id2)
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

            self.assertEqual(len(client.log.select(start=1, limit=10)), 10)
            self.assertEqual(len(client.log.select(start=11, limit=10)), 10)
            self.assertEqual(len(client.log.select(start=21, limit=10)), 10)
            self.assertEqual(len(client.log.select(start=31, limit=10)), 10)
            self.assertEqual(len(client.log.select(start=41, limit=10)), 10)
            self.assertEqual(len(client.log.select(start=51, limit=10)), 10)
            self.assertEqual(len(client.log.select(start=61, limit=10)), 0)

        finally:
            server.stop()


class BankAccountsInterface(NotificationLogInterface):
    @abstractmethod
    def open_account(self, body: str) -> str:
        pass


class BankAccountsJSONService(
    BankAccountsInterface,
    NotificationLogJSONService[BankAccounts],
):
    def open_account(self, request: str) -> str:
        kwargs = json.loads(request)
        account_id = self.app.open_account(**kwargs)
        return json.dumps({"account_id": account_id.hex})


class BankAccountsJSONClient:
    def __init__(self, interface: BankAccountsInterface):
        self.interface = interface
        self.log = NotificationLogJSONClient(interface)

    def open_account(self, full_name, email_address) -> UUID:
        body = json.dumps(
            {
                "full_name": full_name,
                "email_address": email_address,
            }
        )
        body = self.interface.open_account(body)
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
            body = bank_accounts_service.open_account(request_msg)
            status = 201
        else:
            body = "Not found: " + self.path
            status = 404
        self.send(body, status)

    def do_GET(self):
        if self.path.startswith("/notifications/"):
            section_id = self.path.split("/")[-1]
            body = bank_accounts_service.get_log_section(section_id)
            status = 200
        elif self.path.startswith("/notifications"):
            args = self.path.split("?")[-1].split("&")
            args = [p.split("=") for p in args]
            args = {p[0]: p[1] for p in args}
            start = int(args["start"])
            limit = int(args["limit"])

            body = bank_accounts_service.get_notifications(start=start, limit=limit)
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


class BankAccountsHTTPClient(BankAccountsInterface):
    def __init__(self, server_address):
        self.connection = HTTPConnection(*server_address)

    def get_log_section(self, section_id: str) -> str:
        return self._request("GET", "/notifications/{}".format(section_id))

    def get_notifications(self, start: int, limit: int) -> str:
        return self._request("GET", f"/notifications?start={start}&limit={limit}")

    def open_account(self, body: str) -> str:
        return self._request("PUT", "/accounts/", body.encode("utf8"))

    def _request(self, method, url, body=None):
        self.connection.request(method, url, body)
        response = self.connection.getresponse()
        return response.read().decode()


bank_accounts_service: BankAccountsInterface


@HTTPApplicationServer.before_first_request
def init_bank_accounts() -> None:
    global bank_accounts_service
    bank_accounts_service = BankAccountsJSONService(BankAccounts())
