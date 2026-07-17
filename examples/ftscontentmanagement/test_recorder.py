from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar
from unittest import TestCase
from uuid import uuid4

from eventsourcing.postgres import PostgresDatastore
from eventsourcing.sqlite import SQLiteDatastore
from eventsourcing.tests.postgres_utils import drop_tables
from eventsourcing.utils import get_topic
from examples.contentmanagement.application import PageNotFoundError
from examples.ftscontentmanagement.persistence import FtsRecorder, PageInfo
from examples.ftscontentmanagement.postgres import (
    PostgresFtsApplicationRecorder,
    PostgresFtsRecorder,
)
from examples.ftscontentmanagement.sqlite import SQLiteFtsRecorder


class FtsRecorderTestCase(TestCase, ABC):
    env: ClassVar[dict[str, str]] = {}

    def test_recorder(self) -> None:
        recorder = self.construct_recorder()

        # Search pages - nothing found.
        pages = recorder.search_pages("something")
        self.assertEqual(len(pages), 0)

        # Insert a page.
        page_id1 = str(uuid4())
        recorder.insert_pages([PageInfo(page_id1, "title", "slug", "body1")])

        # Select page.
        page = recorder.select_page(page_id1)
        self.assertEqual(page.id, page_id1)
        self.assertEqual(page.slug, "slug")
        self.assertEqual(page.title, "title")
        self.assertEqual(page.body, "body1")

        # Search pages - should find page.
        page_ids = recorder.search_pages("body1")
        self.assertEqual(len(page_ids), 1)
        self.assertEqual(page_ids[0], page_id1)

        # Update page.
        recorder.update_pages([PageInfo(page_id1, "title", "slug", "body2")])

        # Select page - should get updated body.
        page = recorder.select_page(page_id1)
        self.assertEqual(page.id, page_id1)
        self.assertEqual(page.slug, "slug")
        self.assertEqual(page.title, "title")
        self.assertEqual(page.body, "body2")

        # Search pages - query for original body, not found.
        page_ids = recorder.search_pages("body1")
        self.assertEqual(len(page_ids), 0)

        # Search pages - query for updated body.
        page_ids = recorder.search_pages("body2")
        self.assertEqual(len(page_ids), 1)

        # Select page - page not found.
        with self.assertRaises(PageNotFoundError):
            recorder.select_page(uuid4())

    @abstractmethod
    def construct_recorder(self) -> FtsRecorder:
        pass


class TestWithSQLite(FtsRecorderTestCase):
    def construct_recorder(self) -> FtsRecorder:
        recorder = SQLiteFtsRecorder(SQLiteDatastore(":memory:"))
        recorder.create_table()
        return recorder


class TestWithPostgres(FtsRecorderTestCase):
    env: ClassVar[dict[str, str]] = {
        "PERSISTENCE_MODULE": "eventsourcing.postgres",
        "APPLICATION_RECORDER_TOPIC": get_topic(PostgresFtsApplicationRecorder),
    }

    def setUp(self) -> None:
        drop_tables()
        super().setUp()

    def tearDown(self) -> None:
        super().tearDown()
        drop_tables()

    def construct_recorder(self) -> FtsRecorder:
        datastore = PostgresDatastore(
            "eventsourcing",
            "127.0.0.1",
            "5432",
            "eventsourcing",
            "eventsourcing",  # ,
        )
        recorder = PostgresFtsRecorder(datastore)
        recorder.create_table()
        return recorder


del FtsRecorderTestCase
