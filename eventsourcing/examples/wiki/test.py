from unittest import TestCase

from eventsourcing.examples.wiki.application import (
    PageNotFound,
    WikiApplication,
)


class TestWiki(TestCase):
    def test(self) -> None:
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

        # Update the title.
        app.update_title(slug="welcome", title="Welcome Visitors")

        # Check the title was updated.
        page = app.get_page(slug="welcome")
        self.assertEqual(page["title"], "Welcome Visitors")

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
