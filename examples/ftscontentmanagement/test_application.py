from __future__ import annotations

from typing import ClassVar, override
from unittest import TestCase
from uuid import uuid4

from eventsourcing.metadata import put_metadata_in_context
from eventsourcing.tests.postgres_utils import drop_tables
from eventsourcing.utils import get_topic
from examples.ftscontentmanagement.application import FtsContentManagement
from examples.ftscontentmanagement.postgres import PostgresFtsApplicationRecorder
from examples.ftscontentmanagement.sqlite import SQLiteFtsApplicationRecorder


class FtsContentManagementTestCase(TestCase):
    env: ClassVar[dict[str, str]] = {}

    def test_app(self) -> None:

        app = FtsContentManagement(env=self.env)

        # Set user_id context variable.
        user_id = uuid4()
        # Create empty pages.
        with put_metadata_in_context({"user_id": str(user_id)}):
            app.create_page(title="Animals", slug="animals")
            app.create_page(title="Plants", slug="plants")
            app.create_page(title="Minerals", slug="minerals")

        # Search, expect no results.
        self.assertEqual(0, len(app.search("dog")))
        self.assertEqual(0, len(app.search("rose")))
        self.assertEqual(0, len(app.search("zinc")))

        # Update the pages.
        with put_metadata_in_context({"user_id": str(user_id)}):
            app.update_body(slug="animals", body="cat dog zebra")
            app.update_body(slug="plants", body="bluebell rose jasmine")
            app.update_body(slug="minerals", body="iron zinc calcium")

        # Search for single words, expect results.
        pages = app.search("dog")
        self.assertEqual(1, len(pages))
        self.assertEqual(pages[0]["slug"], "animals")
        self.assertEqual(pages[0]["body"], "cat dog zebra")

        pages = app.search("rose")
        self.assertEqual(1, len(pages))
        self.assertEqual(pages[0]["slug"], "plants")
        self.assertEqual(pages[0]["body"], "bluebell rose jasmine")

        pages = app.search("zinc")
        self.assertEqual(1, len(pages))
        self.assertEqual(pages[0]["slug"], "minerals")
        self.assertEqual(pages[0]["body"], "iron zinc calcium")

        # Search for multiple words in same page.
        pages = app.search("dog cat")
        self.assertEqual(1, len(pages))
        self.assertEqual(pages[0]["slug"], "animals")
        self.assertEqual(pages[0]["body"], "cat dog zebra")

        # Search for multiple words in same page, expect no results.
        pages = app.search("rose zebra")
        self.assertEqual(0, len(pages))

        # Search for alternative words, expect two results.
        pages = app.search("rose OR zebra")
        self.assertEqual(2, len(pages))
        self.assertEqual(["animals", "plants"], sorted(p["slug"] for p in pages))


class TestWithSQLite(FtsContentManagementTestCase):
    env: ClassVar[dict[str, str]] = {
        "PERSISTENCE_MODULE": "eventsourcing.sqlite",
        "APPLICATION_RECORDER_TOPIC": get_topic(SQLiteFtsApplicationRecorder),
        "SQLITE_DBNAME": ":memory:",
    }


class TestWithPostgres(FtsContentManagementTestCase):
    env: ClassVar[dict[str, str]] = {
        "PERSISTENCE_MODULE": "eventsourcing.postgres",
        "POSTGRES_DBNAME": "eventsourcing",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "eventsourcing",
        "POSTGRES_PASSWORD": "eventsourcing",
        "APPLICATION_RECORDER_TOPIC": get_topic(PostgresFtsApplicationRecorder),
    }

    @override
    def setUp(self) -> None:
        drop_tables()
        super().setUp()

    @override
    def tearDown(self) -> None:
        super().tearDown()
        drop_tables()


del FtsContentManagementTestCase
