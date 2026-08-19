from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from eventsourcing.sqlite import (
    SQLiteApplicationRecorder,
    SQLiteCursor,
    SQLiteDatastore,
    SQLiteRecorder,
)
from examples.contentmanagement.application import PageNotFoundError
from examples.ftscontentmanagement.persistence import FtsRecorder, PageInfo

if TYPE_CHECKING:
    from collections.abc import Sequence

    from eventsourcing.persistence import StoredEvent


class SQLiteFtsRecorder(FtsRecorder, SQLiteRecorder):
    def __init__(
        self,
        datastore: SQLiteDatastore,
        **kwargs: Any,
    ):
        super().__init__(datastore, **kwargs)
        self.fts_table_name = "ftsprojection"
        self.pages_virtual_table_name = self.fts_table_name + "_fts"

        self.create_table_statements.append(
            "CREATE TABLE IF NOT EXISTS "
            f"{self.fts_table_name} ("
            "page_id TEXT, "
            "page_slug TEXT, "
            "page_title TEXT, "
            "page_body TEXT, "
            "PRIMARY KEY "
            "(page_id)) "
        )
        self.create_table_statements.append(
            f"CREATE VIRTUAL TABLE {self.pages_virtual_table_name} USING fts5("
            f"page_id, page_body, content='{self.fts_table_name}')"
        )
        self.create_table_statements.append(
            "CREATE TRIGGER projection_ai AFTER INSERT ON "
            f"{self.fts_table_name} BEGIN "
            f"INSERT INTO {self.pages_virtual_table_name} "
            "(rowid, page_id, page_body) "
            "VALUES (new.rowid, new.page_id, new.page_body); "
            "END"
        )
        self.create_table_statements.append(
            "CREATE TRIGGER projection_au AFTER UPDATE ON "
            f"{self.fts_table_name} "
            "BEGIN "
            f"INSERT INTO {self.pages_virtual_table_name} "
            f"({self.pages_virtual_table_name}, rowid, page_id, page_body) "
            "VALUES ('delete', old.rowid, old.page_id, old.page_body);"
            f"INSERT INTO {self.pages_virtual_table_name} "
            "(rowid, page_id, page_body) "
            "VALUES (new.rowid, new.page_id, new.page_body); "
            "END"
        )

        self.select_page_statement = (
            "SELECT page_slug, page_title, page_body FROM "
            f"{self.fts_table_name} WHERE page_id = ?"
        )
        self.select_page_from_virtual_table_statement = (
            "SELECT page_body FROM "
            f"{self.pages_virtual_table_name} WHERE page_id = ?"
        )
        self.insert_page_statement = (
            f"INSERT INTO {self.fts_table_name} VALUES (?, ?, ?, ?)"
        )
        self.update_page_statement = (
            f"UPDATE {self.fts_table_name} "
            "SET page_slug = ?, page_title = ?, page_body = ? WHERE page_id = ?"
        )
        self.search_pages_statement = (
            f"SELECT page_id FROM {self.pages_virtual_table_name} "
            f"WHERE page_body MATCH ?"
        )

    @override
    def insert_pages(self, pages: Sequence[PageInfo]) -> None:
        with self.datastore.transaction(commit=True) as c:
            self._insert_pages(c, pages=pages)

    def _insert_pages(self, c: SQLiteCursor, pages: Sequence[PageInfo]) -> None:
        for page in pages:
            c.execute(
                self.insert_page_statement,
                (page.id, page.slug, page.title, page.body),
            )

    @override
    def update_pages(self, pages: Sequence[PageInfo]) -> None:
        with self.datastore.transaction(commit=True) as c:
            self._update_pages(c, pages=pages)

    def _update_pages(self, c: SQLiteCursor, pages: Sequence[PageInfo]) -> None:
        for page in pages:
            c.execute(
                self.update_page_statement,
                (page.slug, page.title, page.body, page.id),
            )

    @override
    def search_pages(self, query: str) -> list[str]:
        with self.datastore.transaction(commit=False) as c:
            c.execute(self.search_pages_statement, [query])
            return [row["page_id"] for row in c.fetchall()]

    @override
    def select_page(self, page_id: str) -> PageInfo:
        with self.datastore.transaction(commit=False) as c:
            c.execute(self.select_page_statement, [page_id])
            for row in c.fetchall():
                return PageInfo(
                    id=page_id,
                    slug=row["page_slug"],
                    title=row["page_title"],
                    body=row["page_body"],
                )
        msg = f"Page ID {page_id} not found"
        raise PageNotFoundError(msg)


class SQLiteFtsApplicationRecorder(SQLiteFtsRecorder, SQLiteApplicationRecorder):
    @override
    def _insert_events(
        self,
        c: SQLiteCursor,
        stored_events: Sequence[StoredEvent],
        *,
        insert_pages: Sequence[PageInfo] = (),
        update_pages: Sequence[PageInfo] = (),
        **kwargs: Any,
    ) -> int | None:
        notification_id = super()._insert_events(c, stored_events, **kwargs)
        self._insert_pages(c, pages=insert_pages)
        self._update_pages(c, pages=update_pages)
        return notification_id
