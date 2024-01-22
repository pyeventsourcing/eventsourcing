from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Sequence, Tuple

from eventsourcing.examples.contentmanagement.application import PageNotFoundError
from eventsourcing.examples.searchablecontent.persistence import (
    SearchableContentRecorder,
)
from eventsourcing.postgres import (
    Factory,
    PostgresAggregateRecorder,
    PostgresApplicationRecorder,
)

if TYPE_CHECKING:  # pragma: nocover
    from uuid import UUID

    from psycopg import Cursor
    from psycopg.rows import DictRow

    from eventsourcing.persistence import StoredEvent


class PostgresSearchableContentRecorder(
    SearchableContentRecorder,
    PostgresAggregateRecorder,
):
    pages_table_name = "pages_projection_example"
    select_page_statement = (
        f"SELECT page_slug, page_title, page_body FROM {pages_table_name}"
        " WHERE page_id = %s"
    )

    insert_page_statement = f"INSERT INTO {pages_table_name} VALUES (%s, %s, %s, %s)"

    update_page_statement = (
        f"UPDATE {pages_table_name}"
        " SET page_slug = %s, page_title = %s, page_body = %s WHERE page_id = %s"
    )

    search_pages_statement = (
        f"SELECT page_id FROM {pages_table_name} WHERE"
        " to_tsvector('english', page_body) @@ websearch_to_tsquery('english', %s)"
    )

    def construct_create_table_statements(self) -> List[str]:
        statements = super().construct_create_table_statements()
        statements.append(
            "CREATE TABLE IF NOT EXISTS "
            f"{self.pages_table_name} ("
            "page_id uuid, "
            "page_slug text, "
            "page_title text, "
            "page_body text, "
            "PRIMARY KEY "
            "(page_id))"
        )
        statements.append(
            f"CREATE INDEX IF NOT EXISTS {self.pages_table_name}_idx "
            f"ON {self.pages_table_name} "
            "USING GIN (to_tsvector('english', page_body))"
        )
        return statements

    def _insert_events(
        self,
        c: Cursor[DictRow],
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> None:
        self._insert_pages(c, **kwargs)
        self._update_pages(c, **kwargs)
        super()._insert_events(c, stored_events, **kwargs)

    def _insert_pages(
        self,
        c: Cursor[DictRow],
        insert_pages: Sequence[Tuple[UUID, str, str, str]] = (),
        **_: Any,
    ) -> None:
        for params in insert_pages:
            c.execute(self.insert_page_statement, params, prepare=True)

    def _update_pages(
        self,
        c: Cursor[DictRow],
        update_pages: Sequence[Tuple[UUID, str, str, str]] = (),
        **_: Any,
    ) -> None:
        for page_id, page_slug, page_title, page_body in update_pages:
            params = (page_slug, page_title, page_body, page_id)
            c.execute(self.update_page_statement, params, prepare=True)

    def search_pages(self, query: str) -> List[UUID]:
        with self.datastore.transaction(commit=False) as curs:
            curs.execute(self.search_pages_statement, [query], prepare=True)
            return [row["page_id"] for row in curs.fetchall()]

    def select_page(self, page_id: UUID) -> Tuple[str, str, str]:
        with self.datastore.transaction(commit=False) as curs:
            curs.execute(self.select_page_statement, [str(page_id)], prepare=True)
            for row in curs.fetchall():
                return row["page_slug"], row["page_title"], row["page_body"]
        msg = f"Page ID {page_id} not found"
        raise PageNotFoundError(msg)


class SearchableContentApplicationRecorder(
    PostgresSearchableContentRecorder, PostgresApplicationRecorder
):
    pass


class SearchableContentInfrastructureFactory(Factory):
    application_recorder_class = SearchableContentApplicationRecorder


del Factory
