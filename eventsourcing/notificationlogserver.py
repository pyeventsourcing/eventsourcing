from http.client import HTTPConnection
from http.server import (
    BaseHTTPRequestHandler,
    HTTPServer,
)
from threading import Event, Thread
from typing import Callable, List

from eventsourcing.bankaccountsinterface import (
    BankAccountsJSONAPI,
    BankAccountsAPI,
)
from eventsourcing.test_application import BankAccounts


class HTTPApplicationServer(Thread):
    prepare: List[Callable] = []

    def __init__(self, address, handler):
        super(HTTPApplicationServer, self).__init__(
            daemon=True
        )
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
            request_msg = self.rfile.read(length).decode(
                "utf8"
            )
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
        return self.request(
            "GET", "/notifications/{}".format(section_id)
        )

    def open_account(self, body: str) -> str:
        return self.request(
            "PUT", "/accounts/", body.encode("utf8")
        )

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
