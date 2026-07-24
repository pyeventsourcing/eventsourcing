from __future__ import annotations

import unittest
from typing import ClassVar
from uuid import uuid4

from eventsourcing.domain import put_metadata_in_context
from eventsourcing.postgres import PostgresDatastore
from eventsourcing.projection import ProjectionRunner
from eventsourcing.tests.postgres_utils import drop_tables
from examples.contentmanagement.application import ContentManagement
from examples.ftsprojection.projection import FtsProjection, PostgresFtsView


class TestFtsProjection(unittest.TestCase):
    env: ClassVar[dict[str, str]] = {
        "CONTENTMANAGEMENT_PERSISTENCE_MODULE": "eventsourcing.postgres",
        "CONTENTMANAGEMENT_POSTGRES_DBNAME": "eventsourcing",
        "CONTENTMANAGEMENT_POSTGRES_HOST": "127.0.0.1",
        "CONTENTMANAGEMENT_POSTGRES_PORT": "5432",
        "CONTENTMANAGEMENT_POSTGRES_USER": "eventsourcing",
        "CONTENTMANAGEMENT_POSTGRES_PASSWORD": "eventsourcing",
        "FTSPROJECTION_PERSISTENCE_MODULE": "eventsourcing.postgres",
        "FTSPROJECTION_POSTGRES_DBNAME": "eventsourcing",
        "FTSPROJECTION_POSTGRES_HOST": "127.0.0.1",
        "FTSPROJECTION_POSTGRES_PORT": "5432",
        "FTSPROJECTION_POSTGRES_USER": "eventsourcing",
        "FTSPROJECTION_POSTGRES_PASSWORD": "eventsourcing",
    }

    def test(self) -> None:
        # Construct an instance of the application ("write model").
        write_model = ContentManagement(env=self.env)

        # Construct tracking recorder ("read model").
        read_model = PostgresFtsView(
            datastore=PostgresDatastore(
                dbname="eventsourcing",
                host="127.0.0.1",
                port=5432,
                user="eventsourcing",
                password="eventsourcing",  # noqa:  S106
            ),
            tracking_table_name="ftsprojection_tracking",
        )
        read_model.create_table()

        # Create some content in the write model.
        user_id = uuid4()
        with put_metadata_in_context({"user_id": str(user_id)}):
            write_model.create_page(title="Animals", slug="animals")
            write_model.update_body(slug="animals", body="cat dog zebra")
            write_model.create_page(title="Plants", slug="plants")
            notification_id = write_model.update_body(
                slug="plants", body="bluebell rose jasmine"
            )

        # Wait for the content to be processed (should time out).
        with self.assertRaises(TimeoutError):
            read_model.wait(write_model.context_name, notification_id)

        # Search in the read model, expect no results.
        self.assertEqual(0, len(read_model.search("dog")))
        self.assertEqual(0, len(read_model.search("rose")))
        self.assertEqual(0, len(read_model.search("zinc")))

        # Run the projection (independently of read and write model objects).
        _ = ProjectionRunner(
            application_class=ContentManagement,
            projection_class=FtsProjection,
            view_class=PostgresFtsView,
            env=self.env,
        )

        # Wait for content to be processed (projection catches up).
        read_model.wait(write_model.context_name, notification_id)

        # Search in the read model, expect results.
        pages = read_model.search("dog")
        self.assertEqual(1, len(pages))
        self.assertEqual(pages[0].slug, "animals")
        self.assertEqual(pages[0].body, "cat dog zebra")

        pages = read_model.search("rose")
        self.assertEqual(1, len(pages))
        self.assertEqual(pages[0].slug, "plants")
        self.assertEqual(pages[0].body, "bluebell rose jasmine")

        pages = read_model.search("zinc")
        self.assertEqual(0, len(pages))

        # Search for multiple words in same page.
        pages = read_model.search("dog cat")
        self.assertEqual(1, len(pages))
        self.assertEqual(pages[0].slug, "animals")
        self.assertEqual(pages[0].body, "cat dog zebra")

        # Search for multiple words in same page, expect no results.
        pages = read_model.search("rose zebra")
        self.assertEqual(0, len(pages))

        # Search for alternative words, expect two results.
        pages = read_model.search("rose OR zebra")
        self.assertEqual(2, len(pages))
        self.assertEqual({"animals", "plants"}, {p.slug for p in pages})

        # Create some more content.
        with put_metadata_in_context({"user_id": str(user_id)}):
            write_model.create_page(title="Minerals", slug="minerals")
            notification_id = write_model.update_body(
                slug="minerals", body="iron zinc calcium"
            )

        # Wait for content to be processed (projection continues processing).
        read_model.wait(write_model.context_name, notification_id)

        # Search for the new content in the read model.
        pages = read_model.search("zinc")
        self.assertEqual(1, len(pages))
        self.assertEqual(pages[0].slug, "minerals")
        self.assertEqual(pages[0].body, "iron zinc calcium")

    def setUp(self) -> None:
        drop_tables()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        drop_tables()
