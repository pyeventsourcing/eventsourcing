from typing import Any, Dict, List, Optional, Sequence, cast

from eventsourcing.examples.searchablecontent.persistence import (
    SearchableContentRecorder,
)
from eventsourcing.persistence import ApplicationRecorder, StoredEvent
from eventsourcing.sqlite import (
    Factory,
    SQLiteApplicationRecorder,
    SQLiteCursor,
    SQLiteDatastore,
)


class SearchableContentApplicationRecorder(
    SearchableContentRecorder, SQLiteApplicationRecorder
):
    def __init__(
        self,
        datastore: SQLiteDatastore,
        events_table_name: str = "stored_events",
        page_bodies_table_name: str = "page_bodies",
    ):
        self.page_bodies_table_name = page_bodies_table_name
        self.page_bodies_virtual_table_name = page_bodies_table_name + "_fts"
        super().__init__(datastore, events_table_name)
        self.insert_page_body_statement = (
            f"INSERT INTO {self.page_bodies_table_name} VALUES (?, ?)"
        )
        self.update_page_body_statement = (
            f"UPDATE {self.page_bodies_table_name} "
            f"SET page_body = ? WHERE page_slug = ?"
        )
        self.search_page_body_statement = (
            f"SELECT page_slug FROM {self.page_bodies_virtual_table_name} WHERE "
            f"page_body MATCH $1"
        )

    def construct_create_table_statements(self) -> List[str]:
        statements = super().construct_create_table_statements()
        statements.append(
            "CREATE TABLE IF NOT EXISTS "
            f"{self.page_bodies_table_name} ("
            "page_slug text, "
            "page_body text, "
            "PRIMARY KEY "
            "(page_slug)) "
        )
        statements.append(
            f"CREATE VIRTUAL TABLE {self.page_bodies_virtual_table_name} USING fts5("
            f"page_slug, page_body, content='{self.page_bodies_table_name}')"
        )
        statements.append(
            f"CREATE TRIGGER page_bodies_ai AFTER INSERT ON "
            f"{self.page_bodies_table_name} BEGIN "
            f"INSERT INTO {self.page_bodies_virtual_table_name} "
            f"(rowid, page_slug, page_body) "
            f"VALUES (new.rowid, new.page_slug, new.page_body); "
            f"END"
        )
        statements.append(
            f"CREATE TRIGGER page_bodies_au AFTER UPDATE ON "
            f"{self.page_bodies_table_name} "
            f"BEGIN "
            f"INSERT INTO {self.page_bodies_virtual_table_name} "
            f"({self.page_bodies_virtual_table_name}, rowid, page_slug, page_body) "
            f"VALUES ('delete', old.rowid, old.page_slug, old.page_body);"
            f"INSERT INTO {self.page_bodies_virtual_table_name} "
            f"(rowid, page_slug, page_body) "
            f"VALUES (new.rowid, new.page_slug, new.page_body); "
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

        # Insert page bodies.
        insert_page_bodies = cast(Dict[str, str], kwargs.get("insert_page_bodies"))
        if insert_page_bodies:
            for page_slug, page_body in insert_page_bodies.items():
                c.execute(self.insert_page_body_statement, (page_slug, page_body))

        # Update page bodies.
        update_page_bodies = cast(Dict[str, str], kwargs.get("update_page_bodies"))
        if update_page_bodies:
            for page_slug, page_body in update_page_bodies.items():
                c.execute(self.update_page_body_statement, (page_body, page_slug))
        return notification_ids

    def search_page_bodies(self, query: str) -> List[str]:
        page_slugs = []

        with self.datastore.transaction(commit=False) as c:
            c.execute(self.search_page_body_statement, [query])
            for row in c.fetchall():
                page_slugs.append(row["page_slug"])

        return page_slugs


class SearchableContentInfrastructureFactory(Factory):
    def application_recorder(self) -> ApplicationRecorder:
        recorder = SearchableContentApplicationRecorder(datastore=self.datastore)
        recorder.create_table()
        return recorder


del Factory
