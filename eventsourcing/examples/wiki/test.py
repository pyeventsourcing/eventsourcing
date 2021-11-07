from typing import cast
from unittest import TestCase
from uuid import uuid4

from eventsourcing.examples.wiki.application import (
    PageNotFound,
    WikiApplication,
)
from eventsourcing.examples.wiki.domainmodel import Index, Page, user_id_cvar
from eventsourcing.system import NotificationLogReader


class TestWiki(TestCase):
    def test(self) -> None:

        # Set user_id context variable.
        user_id = uuid4()
        user_id_cvar.set(user_id)

        # Construct application.
        app = WikiApplication()

        # Check the page doesn't exist.
        with self.assertRaises(PageNotFound):
            app.get_page(slug="welcome")

        # Create a page.
        app.create_page(title="Welcome", slug="welcome")

        # Present page identified by the given slug.
        page = app.get_page(slug="welcome")

        # Check we got a dict that has the given title.
        self.assertEqual(page["title"], "Welcome")
        self.assertEqual(page["body"], "")
        # self.assertEqual(page["modified_by"], user_id)

        # Update the title.
        app.update_title(slug="welcome", title="Welcome Visitors")

        # Check the title was updated.
        page = app.get_page(slug="welcome")
        self.assertEqual(page["title"], "Welcome Visitors")
        self.assertEqual(page["modified_by"], user_id)

        # Update the slug.
        app.update_slug(old_slug="welcome", new_slug="welcome-visitors")

        # Check the index was updated.
        with self.assertRaises(PageNotFound):
            app.get_page(slug="welcome")

        page = app.get_page(slug="welcome-visitors")
        self.assertEqual(page["title"], "Welcome Visitors")

        # Update the body.
        app.update_body(slug="welcome-visitors", body="Welcome to my wiki")

        # Check the body was updated.
        page = app.get_page(slug="welcome-visitors")
        self.assertEqual(page["body"], "Welcome to my wiki")

        # Update the body.
        app.update_body(slug="welcome-visitors", body="Welcome to this wiki")

        # Check the body was updated.
        page = app.get_page(slug="welcome-visitors")
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
        page = app.get_page(slug="welcome-visitors")
        self.assertEqual(
            page["body"],
            """
Welcome to this wiki!

This is a wiki about...
""",
        )

        # Check all the Page events have the user_id.
        for notification in NotificationLogReader(app.log).read(start=1):
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
        page = app.get_page(slug="welcome-visitors")
        self.assertEqual(page["title"], "Welcome Visitors")
        self.assertEqual(page["modified_by"], user_id)

        # Check a snapshot was created by now.
        assert app.snapshots
        index = cast(Index, app.repository.get(Index.create_id("welcome-visitors")))
        assert index.ref
        self.assertTrue(len(list(app.snapshots.get(index.ref))))
