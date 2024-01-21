from __future__ import annotations

from typing import cast
from unittest import TestCase
from uuid import uuid4

from eventsourcing.examples.contentmanagement.application import (
    ContentManagementApplication,
    PageNotFoundError,
    SlugConflictError,
)
from eventsourcing.examples.contentmanagement.domainmodel import (
    Index,
    Page,
    user_id_cvar,
)
from eventsourcing.system import NotificationLogReader


class TestContentManagement(TestCase):
    def test(self) -> None:
        # Set user_id context variable.
        user_id = uuid4()
        user_id_cvar.set(user_id)

        # Construct application.
        app = ContentManagementApplication()

        # Check the page doesn't exist.
        with self.assertRaises(PageNotFoundError):
            app.get_page_by_slug(slug="welcome")

        # Check the list of pages is empty.
        pages = list(app.get_pages())
        self.assertEqual(len(pages), 0)

        # Create a page.
        app.create_page(title="Welcome", slug="welcome")

        # Present page identified by the given slug.
        page = app.get_page_by_slug(slug="welcome")

        # Check we got a dict that has the given title and slug.
        self.assertEqual(page["title"], "Welcome")
        self.assertEqual(page["slug"], "welcome")
        self.assertEqual(page["body"], "")
        self.assertEqual(page["modified_by"], user_id)

        # Update the title.
        app.update_title(slug="welcome", title="Welcome Visitors")

        # Check the title was updated.
        page = app.get_page_by_slug(slug="welcome")
        self.assertEqual(page["title"], "Welcome Visitors")
        self.assertEqual(page["modified_by"], user_id)

        # Update the slug.
        app.update_slug(old_slug="welcome", new_slug="welcome-visitors")

        # Check the index was updated.
        with self.assertRaises(PageNotFoundError):
            app.get_page_by_slug(slug="welcome")

        # Check we can get the page by the new slug.
        page = app.get_page_by_slug(slug="welcome-visitors")
        self.assertEqual(page["title"], "Welcome Visitors")
        self.assertEqual(page["slug"], "welcome-visitors")

        # Update the body.
        app.update_body(slug="welcome-visitors", body="Welcome to my wiki")

        # Check the body was updated.
        page = app.get_page_by_slug(slug="welcome-visitors")
        self.assertEqual(page["body"], "Welcome to my wiki")

        # Update the body.
        app.update_body(slug="welcome-visitors", body="Welcome to this wiki")

        # Check the body was updated.
        page = app.get_page_by_slug(slug="welcome-visitors")
        self.assertEqual(page["body"], "Welcome to this wiki")

        # Update the body.
        app.update_body(
            slug="welcome-visitors",
            body="""
Welcome to this wiki!

This is a wiki about...
""",
        )

        # Check the body was updated.
        page = app.get_page_by_slug(slug="welcome-visitors")
        self.assertEqual(
            page["body"],
            """
Welcome to this wiki!

This is a wiki about...
""",
        )

        # Check all the Page events have the user_id.
        for notification in NotificationLogReader(app.notification_log).read(start=1):
            domain_event = app.mapper.to_domain_event(notification)
            if isinstance(domain_event, Page.Event):
                self.assertEqual(domain_event.user_id, user_id)

        # Change user_id context variable.
        user_id = uuid4()
        user_id_cvar.set(user_id)

        # Update the body.
        app.update_body(
            slug="welcome-visitors",
            body="""
Welcome to this wiki!

This is a wiki about us!
""",
        )

        # Check 'modified_by' changed.
        page = app.get_page_by_slug(slug="welcome-visitors")
        self.assertEqual(page["title"], "Welcome Visitors")
        self.assertEqual(page["modified_by"], user_id)

        # Check a snapshot was created by now.
        assert app.snapshots
        index = cast(Index, app.repository.get(Index.create_id("welcome-visitors")))
        assert index.ref
        self.assertTrue(len(list(app.snapshots.get(index.ref))))

        # Create some more pages and list all the pages.
        app.create_page("Page 2", "page-2")
        app.create_page("Page 3", "page-3")
        app.create_page("Page 4", "page-4")
        app.create_page("Page 5", "page-5")

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
        with self.assertRaises(SlugConflictError):
            app.update_slug("page-2", "page-3")

        # Check we can change the slug of a page to one
        # that was previously being used.
        app.update_slug("welcome-visitors", "welcome")

        page = app.get_page_by_slug(slug="welcome")
        self.assertEqual(page["title"], "Welcome Visitors")
        self.assertEqual(page["modified_by"], user_id)
