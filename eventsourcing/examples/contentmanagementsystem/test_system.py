from __future__ import annotations

from typing import Dict
from unittest import TestCase
from uuid import uuid4

from eventsourcing.examples.contentmanagement.application import (
    ContentManagementApplication,
)
from eventsourcing.examples.contentmanagement.domainmodel import user_id_cvar
from eventsourcing.examples.contentmanagementsystem.application import (
    SearchIndexApplication,
)
from eventsourcing.examples.contentmanagementsystem.system import (
    ContentManagementSystem,
)
from eventsourcing.postgres import PostgresDatastore
from eventsourcing.system import SingleThreadedRunner
from eventsourcing.tests.postgres_utils import drop_postgres_table


class ContentManagementSystemTestCase(TestCase):
    env: Dict[str, str] = {}

    def test_system(self) -> None:
        runner = SingleThreadedRunner(system=ContentManagementSystem(), env=self.env)
        runner.start()

        content_management_app = runner.get(ContentManagementApplication)
        search_index_app = runner.get(SearchIndexApplication)

        # Set user_id context variable.
        user_id = uuid4()
        user_id_cvar.set(user_id)

        # Create empty pages.
        content_management_app.create_page(title="Animals", slug="animals")
        content_management_app.create_page(title="Plants", slug="plants")
        content_management_app.create_page(title="Minerals", slug="minerals")

        # Search, expect no results.
        self.assertEqual(0, len(search_index_app.search("cat")))
        self.assertEqual(0, len(search_index_app.search("rose")))
        self.assertEqual(0, len(search_index_app.search("calcium")))

        # Update the pages.
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
        content_management_app.update_body(slug="animals", body="cat dog zebra")
        content_management_app.update_body(slug="plants", body="bluebell rose jasmine")
        content_management_app.update_body(slug="minerals", body="iron zinc calcium")

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
        pages = [content_management_app.get_page_by_id(page_id) for page_id in page_ids]
        self.assertEqual(2, len(pages))
        self.assertEqual(["animals", "plants"], sorted(p["slug"] for p in pages))


class TestWithSQLite(ContentManagementSystemTestCase):
    env = {
        "PERSISTENCE_MODULE": "eventsourcing.examples.contentmanagementsystem.sqlite",
        "SQLITE_DBNAME": ":memory:",
    }


class TestWithPostgres(ContentManagementSystemTestCase):
    env = {
        "PERSISTENCE_MODULE": "eventsourcing.examples.contentmanagementsystem.postgres",
        "POSTGRES_DBNAME": "eventsourcing",
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "eventsourcing",
        "POSTGRES_PASSWORD": "eventsourcing",
    }

    def setUp(self) -> None:
        super().setUp()
        self.drop_tables()

    def tearDown(self) -> None:
        self.drop_tables()
        super().tearDown()

    def drop_tables(self) -> None:
        db = PostgresDatastore(
            self.env["POSTGRES_DBNAME"],
            self.env["POSTGRES_HOST"],
            self.env["POSTGRES_PORT"],
            self.env["POSTGRES_USER"],
            self.env["POSTGRES_PASSWORD"],
        )
        drop_postgres_table(db, "public.contentmanagementapplication_events")
        drop_postgres_table(db, "public.pages_projection_example")
        drop_postgres_table(db, "public.searchindexapplication_events")
        drop_postgres_table(db, "public.searchindexapplication_tracking")
        db.close()


del ContentManagementSystemTestCase
