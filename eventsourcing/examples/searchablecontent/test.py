import os
from unittest import TestCase
from uuid import uuid4

from eventsourcing.examples.searchablecontent.application import SearchableWikiApplication
from eventsourcing.examples.wiki.domainmodel import user_id_cvar
from eventsourcing.postgres import PostgresDatastore
from eventsourcing.tests.postgres_utils import drop_postgres_table


class TestSearchableWiki(TestCase):
    def test(self) -> None:

        # Set user_id context variable.
        user_id = uuid4()
        user_id_cvar.set(user_id)

        # Construct application.
        app = SearchableWikiApplication()

        # Create empty pages.
        app.create_page(title="Animals", slug="animals")
        app.create_page(title="Plants", slug="plants")
        app.create_page(title="Minerals", slug="minerals")

        # Search, expect no results.
        self.assertEqual(0, len(app.search("dog")))
        self.assertEqual(0, len(app.search("rose")))
        self.assertEqual(0, len(app.search("zinc")))

        # Update the pages.
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

    def setUp(self) -> None:
        super().setUp()
        os.environ["POSTGRES_DBNAME"] = "eventsourcing"
        os.environ["POSTGRES_HOST"] = "127.0.0.1"
        os.environ["POSTGRES_PORT"] = "5432"
        os.environ["POSTGRES_USER"] = "eventsourcing"
        os.environ["POSTGRES_PASSWORD"] = "eventsourcing"
        self.drop_tables()

    def tearDown(self) -> None:
        self.drop_tables()
        super().tearDown()

    def drop_tables(self) -> None:
        db = PostgresDatastore(
            os.environ["POSTGRES_DBNAME"],
            os.environ["POSTGRES_HOST"],
            os.environ["POSTGRES_PORT"],
            os.environ["POSTGRES_USER"],
            os.environ["POSTGRES_PASSWORD"],
        )
        drop_postgres_table(db, "public.searchablewikiapplication_events")
        drop_postgres_table(db, "public.searchablewikiapplication_page_bodies")
        db.close()
