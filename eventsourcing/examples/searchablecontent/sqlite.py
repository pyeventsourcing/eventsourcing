from typing import Any, List, Optional, Sequence, Tuple
from uuid import UUID

from eventsourcing.examples.contentmanagement.application import PageNotFound
from eventsourcing.examples.searchablecontent.persistence import (
    SearchableContentRecorder,
)
from eventsourcing.persistence import StoredEvent
from eventsourcing.sqlite import (
    Factory,
    SQLiteAggregateRecorder,
    SQLiteApplicationRecorder,
    SQLiteCursor,
)


class SQLiteSearchableContentRecorder(
    SearchableContentRecorder, SQLiteAggregateRecorder
):
    pages_table_name = "pages_projection_example"
    pages_virtual_table_name = pages_table_name + "_fts"
    select_page_statement = (
        f"SELECT page_slug, page_title, page_body FROM "
        f"{pages_table_name} WHERE page_id = ?"
    )
    insert_page_statement = f"INSERT INTO {pages_table_name} VALUES (?, ?, ?, ?)"
    update_page_statement = (
        f"UPDATE {pages_table_name} "
        f"SET page_slug = ?, page_title = ?, page_body = ? WHERE page_id = ?"
    )
    search_pages_statement = (
        f"SELECT page_id FROM {pages_virtual_table_name} WHERE " f"page_body MATCH ?"
    )

    def construct_create_table_statements(self) -> List[str]:
        statements = super().construct_create_table_statements()
        statements.append(
            "CREATE TABLE IF NOT EXISTS "
            f"{self.pages_table_name} ("
            "page_id TEXT, "
            "page_slug TEXT, "
            "page_title TEXT, "
            "page_body TEXT, "
            "PRIMARY KEY "
            "(page_id)) "
        )
        statements.append(
            f"CREATE VIRTUAL TABLE {self.pages_virtual_table_name} USING fts5("
            f"page_id, page_body, content='{self.pages_table_name}')"
        )
        statements.append(
            f"CREATE TRIGGER projection_ai AFTER INSERT ON "
            f"{self.pages_table_name} BEGIN "
            f"INSERT INTO {self.pages_virtual_table_name} "
            f"(rowid, page_id, page_body) "
            f"VALUES (new.rowid, new.page_id, new.page_body); "
            f"END"
        )
        statements.append(
            f"CREATE TRIGGER projection_au AFTER UPDATE ON "
            f"{self.pages_table_name} "
            f"BEGIN "
            f"INSERT INTO {self.pages_virtual_table_name} "
            f"({self.pages_virtual_table_name}, rowid, page_id, page_body) "
            f"VALUES ('delete', old.rowid, old.page_id, old.page_body);"
            f"INSERT INTO {self.pages_virtual_table_name} "
            f"(rowid, page_id, page_body) "
            f"VALUES (new.rowid, new.page_id, new.page_body); "
            f"END"
        )
        return statements

    def _insert_events(
        self,
        c: SQLiteCursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Optional[Sequence[int]]:
        notification_ids = super()._insert_events(c, stored_events, **kwargs)
        self._insert_pages(c, **kwargs)
        self._update_pages(c, **kwargs)
        return notification_ids

    def _insert_pages(
        self,
        c: SQLiteCursor,
        insert_pages: Sequence[Tuple[UUID, str, str, str]] = (),
        **_: Any,
    ) -> None:
        for page_id, page_slug, page_title, page_body in insert_pages:
            c.execute(
                self.insert_page_statement,
                (str(page_id), page_slug, page_title, page_body),
            )

    def _update_pages(
        self,
        c: SQLiteCursor,
        update_pages: Sequence[Tuple[UUID, str, str, str]] = (),
        **_: Any,
    ) -> None:
        for page_id, page_slug, page_title, page_body in update_pages:
            c.execute(
                self.update_page_statement,
                (page_slug, page_title, page_body, str(page_id)),
            )

    def search_pages(self, query: str) -> List[UUID]:
        page_slugs = []

        with self.datastore.transaction(commit=False) as c:
            c.execute(self.search_pages_statement, [query])
            for row in c.fetchall():
                page_slugs.append(UUID(row["page_id"]))

        return page_slugs

    def select_page(self, page_id: UUID) -> Tuple[str, str, str]:
        with self.datastore.transaction(commit=False) as c:
            c.execute(self.select_page_statement, [str(page_id)])
            for row in c.fetchall():
                return row["page_slug"], row["page_title"], row["page_body"]
        raise PageNotFound(f"Page ID {page_id} not found")


class SearchableContentApplicationRecorder(
    SQLiteSearchableContentRecorder, SQLiteApplicationRecorder
):
    pass


class SearchableContentInfrastructureFactory(Factory):
    application_recorder_class = SearchableContentApplicationRecorder


del Factory
