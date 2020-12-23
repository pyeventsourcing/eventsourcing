import threading
from threading import Thread
from time import sleep
from unittest.case import TestCase

from eventsourcing.bankaccounts import BankAccounts
from eventsourcing.notificationlogserver import (
    BankAccountsHTTPClient,
    BankAccountsHTTPHandler,
    HTTPApplicationServer,
)
from eventsourcing.bankaccountsinterface import (
    BankAccountsJSONClient,
    BankAccountsJSONAPI,
)


class TestRemoteNotificationLog(TestCase):
    def test_directly(self):
        client = BankAccountsJSONClient(
            BankAccountsJSONAPI(BankAccounts())
        )
        account_id1 = client.open_account(
            "Alice", "alice@example.com"
        )
        account_id2 = client.open_account(
            "Bob", "bob@example.com"
        )

        # Get the "first" section of log.
        section = client.log["1,10"]
        self.assertEqual(len(section.items), 2)
        self.assertEqual(
            section.items[0].originator_id, account_id1
        )
        self.assertEqual(
            section.items[1].originator_id, account_id2
        )

    def test_with_http(self):
        server_address = ("", 8000)

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
                BankAccountsHTTPClient(
                    server_address=server_address
                )
            )

            account_id1 = client.open_account(
                "Alice", "alice@example.com"
            )
            account_id2 = client.open_account(
                "Bob", "bob@example.com"
            )

            # Get the "first" section of log.
            section = client.log["1,10"]
            self.assertEqual(len(section.items), 2)
            self.assertEqual(
                section.items[0].originator_id, account_id1
            )
            self.assertEqual(
                section.items[1].originator_id, account_id2
            )
        finally:
            server.stop()

    def test_with_http_and_threads(self):
        server_address = ("", 8000)

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
                    BankAccountsHTTPClient(
                        server_address=server_address
                    )
                )
                for _ in range(30):
                    try:
                        account_id1 = client.open_account(
                            "Alice", "alice@example.com"
                        )
                        # print(threading.get_ident(), account_id1)
                    except Exception as e:
                        print(
                            threading.get_ident(), "error:", e
                        )
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
                BankAccountsHTTPClient(
                    server_address=server_address
                )
            )
            self.assertEqual(len(client.log["1,10"].items), 10)
            self.assertEqual(
                len(client.log["11,20"].items), 10
            )
            self.assertEqual(
                len(client.log["21,30"].items), 10
            )
            self.assertEqual(
                len(client.log["31,40"].items), 10
            )
            self.assertEqual(
                len(client.log["41,50"].items), 10
            )
            self.assertEqual(
                len(client.log["51,60"].items), 10
            )
            self.assertEqual(len(client.log["61,70"].items), 0)

        finally:
            server.stop()
