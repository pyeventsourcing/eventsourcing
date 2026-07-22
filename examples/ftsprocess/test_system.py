from __future__ import annotations

from typing import ClassVar
from unittest import TestCase
from uuid import uuid4

from eventsourcing.domain import put_metadata_in_context
from eventsourcing.pydantic import Decision
from eventsourcing.system import SingleThreadedRunner
from eventsourcing.tests.postgres_utils import drop_tables
from eventsourcing.utils import get_topic
from examples.contentmanagement.application import ContentManagement
from examples.ftsprocess.application import FtsProcess
from examples.ftsprocess.postgres import PostgresFtsProcessRecorder
from examples.ftsprocess.sqlite import SQLiteFtsProcessRecorder
from examples.ftsprocess.system import ContentManagementSystem


class ContentManagementSystemTestCase(TestCase):
    env: ClassVar[dict[str, str]] = {}

    def test_system(self) -> None:
        with SingleThreadedRunner[Decision](
            system=ContentManagementSystem(), env=self.env
        ) as runner:

            content_management_app = runner.get(ContentManagement)
            search_index_app = runner.get(FtsProcess)

            # Set user_id context variable.
            user_id = uuid4()
            with put_metadata_in_context({"user_id": str(user_id)}):
                # Create empty pages.
                content_management_app.create_page(title="Animals", slug="animals")
                content_management_app.create_page(title="Plants", slug="plants")
                content_management_app.create_page(title="Minerals", slug="minerals")

            # Search, expect no results.
            self.assertEqual(0, len(search_index_app.search("cat")))
            self.assertEqual(0, len(search_index_app.search("rose")))
            self.assertEqual(0, len(search_index_app.search("calcium")))

            # Update the pages.
            with put_metadata_in_context({"user_id": str(user_id)}):
                content_management_app.update_body(slug="animals", body="cat")
                content_management_app.update_body(slug="plants", body="rose")
                content_management_app.update_body(slug="minerals", body="calcium")

            # Search for single words.
            page_ids = search_index_app.search("cat")
            self.assertEqual(1, len(page_ids))
            page = content_management_app.get_page_by_id(page_ids[0])
            self.assertEqual(page["slug"], "animals")
            self.assertEqual(page["body"], "cat")

            page_ids = search_index_app.search("rose")
            self.assertEqual(1, len(page_ids))
            page = content_management_app.get_page_by_id(page_ids[0])
            self.assertEqual(page["slug"], "plants")
            self.assertEqual(page["body"], "rose")

            page_ids = search_index_app.search("calcium")
            self.assertEqual(1, len(page_ids))
            page = content_management_app.get_page_by_id(page_ids[0])
            self.assertEqual(page["slug"], "minerals")
            self.assertEqual(page["body"], "calcium")

            self.assertEqual(len(search_index_app.search("dog")), 0)
            self.assertEqual(len(search_index_app.search("bluebell")), 0)
            self.assertEqual(len(search_index_app.search("zinc")), 0)

            # Update the pages again.
            with put_metadata_in_context({"user_id": str(user_id)}):
                content_management_app.update_body(slug="animals", body="cat dog zebra")
                content_management_app.update_body(
                    slug="plants", body="bluebell rose jasmine"
                )
                content_management_app.update_body(
                    slug="minerals", body="iron zinc calcium"
                )

            # Search for single words.
            page_ids = search_index_app.search("cat")
            self.assertEqual(1, len(page_ids))
            page = content_management_app.get_page_by_id(page_ids[0])
            self.assertEqual(page["slug"], "animals")
            self.assertEqual(page["body"], "cat dog zebra")

            page_ids = search_index_app.search("rose")
            self.assertEqual(1, len(page_ids))
            page = content_management_app.get_page_by_id(page_ids[0])
            self.assertEqual(page["slug"], "plants")
            self.assertEqual(page["body"], "bluebell rose jasmine")

            page_ids = search_index_app.search("calcium")
            self.assertEqual(1, len(page_ids))
            page = content_management_app.get_page_by_id(page_ids[0])
            self.assertEqual(page["slug"], "minerals")
            self.assertEqual(page["body"], "iron zinc calcium")

            page_ids = search_index_app.search("dog")
            self.assertEqual(1, len(page_ids))
            page = content_management_app.get_page_by_id(page_ids[0])
            self.assertEqual(page["slug"], "animals")
            self.assertEqual(page["body"], "cat dog zebra")

            page_ids = search_index_app.search("bluebell")
            self.assertEqual(1, len(page_ids))
            page = content_management_app.get_page_by_id(page_ids[0])
            self.assertEqual(page["slug"], "plants")
            self.assertEqual(page["body"], "bluebell rose jasmine")

            page_ids = search_index_app.search("zinc")
            self.assertEqual(1, len(page_ids))
            page = content_management_app.get_page_by_id(page_ids[0])
            self.assertEqual(page["slug"], "minerals")
            self.assertEqual(page["body"], "iron zinc calcium")

            # Search for multiple words in same page.
            page_ids = search_index_app.search("dog cat")
            self.assertEqual(1, len(page_ids))
            page = content_management_app.get_page_by_id(page_ids[0])
            self.assertEqual(page["slug"], "animals")
            self.assertEqual(page["body"], "cat dog zebra")

            # Search for multiple words in same page, expect no results.
            page_ids = search_index_app.search("rose zebra")
            self.assertEqual(0, len(page_ids))

            # Search for alternative words, expect two results.
            page_ids = search_index_app.search("rose OR zebra")
            pages = [
                content_management_app.get_page_by_id(page_id) for page_id in page_ids
            ]
            self.assertEqual(2, len(pages))
            self.assertEqual(["animals", "plants"], sorted(p["slug"] for p in pages))


class TestWithSQLite(ContentManagementSystemTestCase):
    env: ClassVar[dict[str, str]] = {
        "PERSISTENCE_MODULE": "eventsourcing.sqlite",
        "PROCESS_RECORDER_TOPIC": get_topic(SQLiteFtsProcessRecorder),
        "SQLITE_DBNAME": ":memory:",
    }


class TestWithPostgres(ContentManagementSystemTestCase):
    env: ClassVar[dict[str, str]] = {
        "PERSISTENCE_MODULE": "eventsourcing.postgres",
        "PROCESS_RECORDER_TOPIC": get_topic(PostgresFtsProcessRecorder),
        "POSTGRES_DBNAME": "eventsourcing",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "eventsourcing",
        "POSTGRES_PASSWORD": "eventsourcing",
    }

    def setUp(self) -> None:
        drop_tables()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        drop_tables()

    def test_system(self) -> None:
        super().test_system()


del ContentManagementSystemTestCase
