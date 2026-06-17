from __future__ import annotations

from typing import cast
from unittest import TestCase
from uuid import uuid4

from eventsourcing.system import NotificationLogReader
from examples.contentmanagement.application import (
    ContentManagement,
    PageNotFoundError,
    SlugConflictError,
)
from examples.contentmanagement.domainmodel import Page, Slug, user_id_cvar


class TestContentManagement(TestCase):
    def test(self) -> None:
        # Construct application.
        app = ContentManagement()

        # Check the page doesn't exist.
        with self.assertRaises(PageNotFoundError):
            app.get_page_by_slug(slug="welcome")

        # Check the list of pages is empty.
        pages = list(app.get_pages())
        self.assertEqual(len(pages), 0)

        # Create a page.
        user_id1 = uuid4()
        user_id_cvar.set(user_id1)
        app.create_page(title="Welcome", slug="welcome")

        # Present page identified by the given slug.
        page = app.get_page_by_slug(slug="welcome")

        # Check we got a dict that has the given title and slug.
        self.assertEqual(page["title"], "Welcome")
        self.assertEqual(page["slug"], "welcome")
        self.assertEqual(page["body"], "")
        self.assertEqual(page["modified_by"], user_id1)

        # Update the title.
        user_id2 = uuid4()
        user_id_cvar.set(user_id2)
        app.update_title(slug="welcome", title="Welcome Visitors")

        # Check the title was updated.
        page = app.get_page_by_slug(slug="welcome")
        self.assertEqual(page["title"], "Welcome Visitors")
        self.assertEqual(page["slug"], "welcome")
        self.assertEqual(page["body"], "")
        self.assertEqual(page["modified_by"], user_id2)

        # Update the slug.
        user_id3 = uuid4()
        user_id_cvar.set(user_id3)
        app.update_slug(old_slug="welcome", new_slug="welcome-visitors")

        # Check the slug was updated.
        with self.assertRaises(PageNotFoundError):
            app.get_page_by_slug(slug="welcome")

        # Check we can get the page by the new slug.
        page = app.get_page_by_slug(slug="welcome-visitors")
        self.assertEqual(page["title"], "Welcome Visitors")
        self.assertEqual(page["slug"], "welcome-visitors")
        self.assertEqual(page["body"], "")
        self.assertEqual(page["modified_by"], user_id3)

        # Update the body.
        user_id4 = uuid4()
        user_id_cvar.set(user_id4)
        app.update_body(slug="welcome-visitors", body="Welcome to my wiki!")

        # Check the body was updated.
        page = app.get_page_by_slug(slug="welcome-visitors")
        self.assertEqual(page["title"], "Welcome Visitors")
        self.assertEqual(page["slug"], "welcome-visitors")
        self.assertEqual(page["body"], "Welcome to my wiki!")
        self.assertEqual(page["modified_by"], user_id4)

        # Check we are on version 4.
        page_id = cast(
            "Slug", app.repository.get(Slug.create_id("welcome-visitors"))
        ).page_id
        assert page_id is not None
        page_aggregate_v4: Page = app.repository.get(page_id)
        self.assertEqual(page_aggregate_v4.version, 4)

        # Check there are no snapshots.
        assert app.snapshots is not None
        self.assertFalse(len(list(app.snapshots.get(page_id))))

        # Update the body (should trigger a snapshot).
        user_id5 = uuid4()
        user_id_cvar.set(user_id5)
        app.update_body(
            slug="welcome-visitors",
            body="""
Welcome to this wiki!

This is a wiki about...
""",
        )

        # Check we are on version 5.
        page_aggregate_v5: Page = app.repository.get(page_id)
        self.assertEqual(page_aggregate_v5.version, 5)

        # Check the body was updated.
        page = app.get_page_by_slug(slug="welcome-visitors")
        self.assertEqual(page["title"], "Welcome Visitors")
        self.assertEqual(page["slug"], "welcome-visitors")
        self.assertEqual(
            page["body"],
            """
Welcome to this wiki!

This is a wiki about...
""",
        )
        self.assertEqual(page["modified_by"], user_id5)

        # Check a snapshot was taken.
        self.assertTrue(len(list(app.snapshots.get(page_id))))

        # Check all the Page events have the correct user IDs.
        user_ids = iter([user_id1, user_id2, user_id3, user_id4, user_id5])
        for notification in NotificationLogReader(app.notification_log).read(start=1):
            domain_event = app.mapper.to_domain_event(notification)
            if isinstance(domain_event, Page.Event):
                self.assertEqual(domain_event.user_id, next(user_ids))

        # Create some more pages.
        app.create_page("Page 2", "page-2")
        app.create_page("Page 3", "page-3")
        app.create_page("Page 4", "page-4")
        app.create_page("Page 5", "page-5")

        # List all the pages.
        pages = list(app.get_pages(desc=True))
        self.assertEqual(pages[0]["title"], "Page 5")
        self.assertEqual(pages[0]["slug"], "page-5")
        self.assertEqual(pages[1]["title"], "Page 4")
        self.assertEqual(pages[1]["slug"], "page-4")
        self.assertEqual(pages[2]["title"], "Page 3")
        self.assertEqual(pages[2]["slug"], "page-3")
        self.assertEqual(pages[3]["title"], "Page 2")
        self.assertEqual(pages[3]["slug"], "page-2")
        self.assertEqual(pages[4]["title"], "Welcome Visitors")
        self.assertEqual(pages[4]["slug"], "welcome-visitors")

        pages = list(app.get_pages(desc=True, limit=3))
        self.assertEqual(len(pages), 3)
        self.assertEqual(pages[0]["slug"], "page-5")
        self.assertEqual(pages[1]["slug"], "page-4")
        self.assertEqual(pages[2]["slug"], "page-3")

        pages = list(app.get_pages(desc=True, limit=3, lte=2))
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0]["slug"], "page-2")
        self.assertEqual(pages[1]["slug"], "welcome-visitors")

        pages = list(app.get_pages(desc=True, lte=2))
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0]["slug"], "page-2")
        self.assertEqual(pages[1]["slug"], "welcome-visitors")

        # Check we can't change the slug of a page to one
        # that is being used by another page.
        app.get_page_by_slug(slug="page-3")
        with self.assertRaises(SlugConflictError):
            app.update_slug("page-2", "page-3")

        # Check we can change the slug of a page to one
        # that was previously being used by another page.
        app.get_page_by_slug(slug="welcome-visitors")
        with self.assertRaises(PageNotFoundError):
            app.get_page_by_slug(slug="welcome")
        slug: Slug = app.repository.get(Slug.create_id("welcome"))
        self.assertIsNone(slug.page_id)

        app.update_slug("welcome-visitors", "welcome")

        page = app.get_page_by_slug(slug="welcome")
        self.assertEqual(page["title"], "Welcome Visitors")
