from __future__ import annotations

from typing import TYPE_CHECKING, Any

from psycopg.sql import SQL, Identifier

from eventsourcing.postgres import (
    PostgresApplicationRecorder,
    PostgresDatastore,
    PostgresRecorder,
)
from examples.contentmanagement.application import PageNotFoundError
from examples.ftscontentmanagement.persistence import FtsRecorder, PageInfo

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from psycopg import Cursor
    from psycopg.rows import DictRow

    from eventsourcing.persistence import StoredEvent


class PostgresFtsRecorder(
    PostgresRecorder,
    FtsRecorder,
):
    def __init__(
        self,
        datastore: PostgresDatastore,
        fts_table_name: str = "ftsprojection",
        **kwargs: Any,
    ):
        super().__init__(datastore, **kwargs)
        self.check_identifier_length(fts_table_name)
        self.fts_table_name = fts_table_name
        self.sql_create_statements.append(
            SQL(
                "CREATE TABLE IF NOT EXISTS "
                "{0}.{1} ("
                "page_id text, "
                "page_slug text, "
                "page_title text, "
                "page_body text, "
                "PRIMARY KEY "
                "(page_id))"
            ).format(
                Identifier(self.datastore.schema),
                Identifier(self.fts_table_name),
            )
        )
        self.sql_create_statements.append(
            SQL(
                "CREATE INDEX IF NOT EXISTS {0} "
                "ON {1}.{2} "
                "USING GIN (to_tsvector('english', page_body))"
            ).format(
                Identifier(self.fts_table_name + "_idx"),
                Identifier(self.datastore.schema),
                Identifier(self.fts_table_name),
            )
        )

        self.select_page_statement = SQL(
            "SELECT page_slug, page_title, page_body FROM {0}.{1} WHERE page_id = %s"
        ).format(
            Identifier(self.datastore.schema),
            Identifier(self.fts_table_name),
        )

        self.insert_page_statement = SQL(
            "INSERT INTO {0}.{1} VALUES (%s, %s, %s, %s)"
        ).format(
            Identifier(self.datastore.schema),
            Identifier(self.fts_table_name),
        )

        self.update_page_statement = SQL(
            "UPDATE {0}.{1} SET "
            "page_slug = %s, "
            "page_title = %s, "
            "page_body = %s "
            "WHERE page_id = %s"
        ).format(
            Identifier(self.datastore.schema),
            Identifier(self.fts_table_name),
        )

        self.search_pages_statement = SQL(
            "SELECT page_id FROM {0}.{1} WHERE "
            "to_tsvector('english', page_body) @@ "
            "websearch_to_tsquery('english', %s)"
        ).format(
            Identifier(self.datastore.schema),
            Identifier(self.fts_table_name),
        )

    def insert_pages(self, pages: Sequence[PageInfo]) -> None:
        with self.datastore.transaction(commit=True) as curs:
            self._insert_pages(curs, pages)

    def update_pages(self, pages: Sequence[PageInfo]) -> None:
        with self.datastore.transaction(commit=True) as curs:
            self._update_pages(curs, pages)

    def _insert_pages(self, curs: Cursor[DictRow], pages: Sequence[PageInfo]) -> None:
        for page in pages:
            params = (page.id, page.slug, page.title, page.body)
            curs.execute(self.insert_page_statement, params, prepare=True)

    def _update_pages(self, curs: Cursor[DictRow], pages: Sequence[PageInfo]) -> None:
        for page in pages:
            params = (page.slug, page.title, page.body, page.id)
            curs.execute(self.update_page_statement, params, prepare=True)

    def search_pages(self, query: str) -> list[str]:
        with self.datastore.transaction(commit=False) as curs:
            curs.execute(self.search_pages_statement, [query], prepare=True)
            return [row["page_id"] for row in curs.fetchall()]

    def select_page(self, page_id: str) -> PageInfo:
        with self.datastore.transaction(commit=False) as curs:
            curs.execute(self.select_page_statement, [str(page_id)], prepare=True)
            for row in curs.fetchall():
                return PageInfo(
                    id=page_id,
                    slug=row["page_slug"],
                    title=row["page_title"],
                    body=row["page_body"],
                )
        msg = f"Page ID {page_id} not found"
        raise PageNotFoundError(msg)


class PostgresFtsApplicationRecorder(PostgresFtsRecorder, PostgresApplicationRecorder):
    def _insert_events(
        self,
        curs: Cursor[DictRow],
        stored_events: Sequence[StoredEvent],
        *,
        insert_pages: Sequence[PageInfo] = (),
        update_pages: Sequence[PageInfo] = (),
        **kwargs: Any,
    ) -> None:
        notification_ids = super()._insert_events(curs, stored_events, **kwargs)
        self._insert_pages(curs, pages=insert_pages)
        self._update_pages(curs, pages=update_pages)
        return notification_ids
