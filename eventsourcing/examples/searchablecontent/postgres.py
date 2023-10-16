from typing import Any, List, Optional, Sequence, Tuple
from uuid import UUID

from eventsourcing.examples.contentmanagement.application import PageNotFound
from eventsourcing.examples.searchablecontent.persistence import (
    SearchableContentRecorder,
)
from eventsourcing.persistence import StoredEvent
from eventsourcing.postgres import (
    Factory,
    PostgresAggregateRecorder,
    PostgresApplicationRecorder,
    PostgresConnection,
    PostgresCursor,
)


class PostgresSearchableContentRecorder(
    SearchableContentRecorder,
    PostgresAggregateRecorder,
):
    pages_table_name = "pages_projection_example"
    select_page_statement = (
        f"SELECT page_slug, page_title, page_body FROM {pages_table_name}"
        f" WHERE page_id = $1"
    )

    select_page_statement_name = f"select_{pages_table_name}".replace(".", "_")

    insert_page_statement = f"INSERT INTO {pages_table_name} VALUES ($1, $2, $3, $4)"
    insert_page_statement_name = f"insert_{pages_table_name}".replace(".", "_")

    update_page_statement = (
        f"UPDATE {pages_table_name} "
        f"SET page_slug = $1, page_title = $2, page_body = $3 WHERE page_id = $4"
    )
    update_page_statement_name = f"update_{pages_table_name}".replace(".", "_")

    search_pages_statement = (
        f"SELECT page_id FROM {pages_table_name} WHERE "
        f"to_tsvector('english', page_body) @@ websearch_to_tsquery('english', $1)"
    )
    search_pages_statement_name = f"search_{pages_table_name}".replace(".", "_")

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
            f"USING GIN (to_tsvector('english', page_body))"
        )
        return statements

    def _prepare_insert_events(self, conn: PostgresConnection) -> None:
        super()._prepare_insert_events(conn)
        self._prepare(conn, self.insert_page_statement_name, self.insert_page_statement)
        self._prepare(conn, self.update_page_statement_name, self.update_page_statement)

    def _insert_events(
        self,
        c: PostgresCursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Optional[Sequence[int]]:
        notification_ids = super()._insert_events(c, stored_events, **kwargs)
        self._insert_pages(c, **kwargs)
        self._update_pages(c, **kwargs)
        return notification_ids

    def _insert_pages(
        self,
        c: PostgresCursor,
        insert_pages: Sequence[Tuple[UUID, str, str, str]] = (),
        **_: Any,
    ) -> None:
        for page_id, page_slug, page_title, page_body in insert_pages:
            statement_alias = self.statement_name_aliases[
                self.insert_page_statement_name
            ]
            c.execute(
                f"EXECUTE {statement_alias}(%s, %s, %s, %s)",
                (
                    page_id,
                    page_slug,
                    page_title,
                    page_body,
                ),
            )

    def _update_pages(
        self,
        c: PostgresCursor,
        update_pages: Sequence[Tuple[UUID, str, str, str]] = (),
        **_: Any,
    ) -> None:
        for page_id, page_slug, page_title, page_body in update_pages:
            statement_alias = self.statement_name_aliases[
                self.update_page_statement_name
            ]
            c.execute(
                f"EXECUTE {statement_alias}(%s, %s, %s, %s)",
                (
                    page_slug,
                    page_title,
                    page_body,
                    page_id,
                ),
            )

    def search_pages(self, query: str) -> List[UUID]:
        page_ids = []

        with self.datastore.get_connection() as conn:
            self._prepare(
                conn,
                self.search_pages_statement_name,
                self.search_pages_statement,
            )
            with conn.transaction(commit=False) as curs:
                statement_alias = self.statement_name_aliases[
                    self.search_pages_statement_name
                ]
                curs.execute(f"EXECUTE {statement_alias}(%s)", [query])
                for row in curs.fetchall():
                    page_ids.append(row["page_id"])

        return page_ids

    def select_page(self, page_id: UUID) -> Tuple[str, str, str]:
        with self.datastore.get_connection() as conn:
            self._prepare(
                conn,
                self.select_page_statement_name,
                self.select_page_statement,
            )
            with conn.transaction(commit=False) as curs:
                statement_alias = self.statement_name_aliases[
                    self.select_page_statement_name
                ]
                curs.execute(f"EXECUTE {statement_alias}(%s)", [str(page_id)])
                for row in curs.fetchall():
                    return row["page_slug"], row["page_title"], row["page_body"]
        raise PageNotFound(f"Page ID {page_id} not found")


class SearchableContentApplicationRecorder(
    PostgresSearchableContentRecorder, PostgresApplicationRecorder
):
    pass


class SearchableContentInfrastructureFactory(Factory):
    application_recorder_class = SearchableContentApplicationRecorder


del Factory
