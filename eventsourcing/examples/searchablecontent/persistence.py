from typing import Any, Dict, List, Optional, Sequence, cast

from eventsourcing.persistence import ApplicationRecorder, StoredEvent
from eventsourcing.postgres import (
    Factory,
    PostgresApplicationRecorder,
    PostgresConnection,
    PostgresCursor,
    PostgresDatastore,
)


class SearchableWikiInfrastructureFactory(Factory):
    def application_recorder(self) -> ApplicationRecorder:
        prefix = (self.datastore.schema + ".") if self.datastore.schema else ""
        prefix += self.env.name.lower() or "stored"
        events_table_name = prefix + "_events"
        page_bodies_table_name = prefix + "_page_bodies"
        recorder = SearchableWikiApplicationRecorder(
            datastore=self.datastore,
            events_table_name=events_table_name,
            page_bodies_table_name=page_bodies_table_name,
        )
        recorder.create_table()
        return recorder


class SearchableWikiApplicationRecorder(PostgresApplicationRecorder):
    def __init__(
        self,
        datastore: PostgresDatastore,
        events_table_name: str = "stored_events",
        page_bodies_table_name: str = "page_bodies",
    ):
        self.check_table_name_length(page_bodies_table_name, datastore.schema)
        self.page_bodies_table_name = page_bodies_table_name
        super().__init__(datastore, events_table_name)
        self.insert_page_body_statement = (
            f"INSERT INTO {self.page_bodies_table_name} VALUES ($1, $2)"
        )
        self.insert_page_body_statement_name = (
            f"insert_{page_bodies_table_name}".replace(".", "_")
        )
        self.update_page_body_statement = (
            f"UPDATE {self.page_bodies_table_name} "
            f"SET page_body = $1 WHERE page_slug = $2"
        )
        self.update_page_body_statement_name = (
            f"update_{page_bodies_table_name}".replace(".", "_")
        )
        self.search_page_body_statement = (
            f"SELECT page_slug FROM {self.page_bodies_table_name} WHERE "
            f"to_tsvector('english', page_body) @@ websearch_to_tsquery('english', $1)"
        )

        self.search_page_body_statement_name = (
            f"search_{page_bodies_table_name}".replace(".", "_")
        )

    def construct_create_table_statements(self) -> List[str]:
        statements = super().construct_create_table_statements()
        statements.append(
            "CREATE TABLE IF NOT EXISTS "
            f"{self.page_bodies_table_name} ("
            "page_slug text, "
            "page_body text, "
            "PRIMARY KEY "
            "(page_slug))"
        )
        statements.append(
            f"CREATE INDEX IF NOT EXISTS {self.page_bodies_table_name}_idx "
            f"ON {self.page_bodies_table_name} "
            f"USING GIN (to_tsvector('english', page_body))"
        )
        return statements

    def _prepare_insert_events(self, conn: PostgresConnection) -> None:
        super()._prepare_insert_events(conn)
        self._prepare(
            conn, self.insert_page_body_statement_name, self.insert_page_body_statement
        )
        self._prepare(
            conn, self.update_page_body_statement_name, self.update_page_body_statement
        )

    def _insert_events(
        self,
        c: PostgresCursor,
        stored_events: List[StoredEvent],
        **kwargs: Any,
    ) -> Optional[Sequence[int]]:
        notification_ids = super()._insert_events(c, stored_events, **kwargs)

        # Insert page bodies.
        insert_page_bodies = cast(Dict[str, str], kwargs.get("insert_page_bodies"))
        if insert_page_bodies:
            for page_slug, page_body in insert_page_bodies.items():
                statement_alias = self.statement_name_aliases[
                    self.insert_page_body_statement_name
                ]
                c.execute(
                    f"EXECUTE {statement_alias}(%s, %s)",
                    (
                        page_slug,
                        page_body,
                    ),
                )

        # Update page bodies.
        update_page_bodies = cast(Dict[str, str], kwargs.get("update_page_bodies"))
        if update_page_bodies:
            for page_slug, page_body in update_page_bodies.items():
                statement_alias = self.statement_name_aliases[
                    self.update_page_body_statement_name
                ]
                c.execute(
                    f"EXECUTE {statement_alias}(%s, %s)",
                    (
                        page_body,
                        page_slug,
                    ),
                )
        return notification_ids

    def search_page_bodies(self, query: str) -> List[str]:
        page_slugs = []

        with self.datastore.get_connection() as conn:
            self._prepare(
                conn, self.search_page_body_statement_name,
                self.search_page_body_statement
            )
            with conn.transaction(commit=False) as curs:
                statement_alias = self.statement_name_aliases[
                    self.search_page_body_statement_name
                ]
                curs.execute(f"EXECUTE {statement_alias}(%s)", [query])
                for row in curs.fetchall():
                    page_slugs.append(row["page_slug"])

        return page_slugs
