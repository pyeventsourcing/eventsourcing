import os
from unittest import TestCase

from eventsourcing.tests.application import (
    ApplicationTestCase,
    ExampleApplicationTestCase,
)
from eventsourcing.tests.postgres_utils import drop_tables


class WithPostgres(TestCase):
    expected_factory_topic = "eventsourcing.postgres:PostgresFactory"
    postgres_dbname = "eventsourcing"
    postgres_schema = "public"
    postgres_enable_db_functions = "n"

    def setUp(self) -> None:
        super().setUp()

        os.environ["PERSISTENCE_MODULE"] = "eventsourcing.postgres"
        os.environ["CREATE_TABLE"] = "y"
        os.environ["POSTGRES_DBNAME"] = self.postgres_dbname
        os.environ["POSTGRES_HOST"] = "127.0.0.1"
        os.environ["POSTGRES_PORT"] = "5432"
        os.environ["POSTGRES_USER"] = "eventsourcing"
        os.environ["POSTGRES_PASSWORD"] = "eventsourcing"  # noqa: S105
        os.environ["POSTGRES_SCHEMA"] = self.postgres_schema
        os.environ["POSTGRES_ENABLE_DB_FUNCTIONS"] = self.postgres_enable_db_functions
        drop_tables()

    def tearDown(self) -> None:
        drop_tables()

        del os.environ["PERSISTENCE_MODULE"]
        del os.environ["CREATE_TABLE"]
        del os.environ["POSTGRES_DBNAME"]
        del os.environ["POSTGRES_HOST"]
        del os.environ["POSTGRES_PORT"]
        del os.environ["POSTGRES_USER"]
        del os.environ["POSTGRES_PASSWORD"]
        del os.environ["POSTGRES_SCHEMA"]
        del os.environ["POSTGRES_ENABLE_DB_FUNCTIONS"]

        super().tearDown()


class TestApplicationWithPostgres(WithPostgres, ApplicationTestCase):
    pass


class TestApplicationWithPostgresEnableFunctions(WithPostgres, ApplicationTestCase):
    pass


class TestApplicationWithPostgresSchemaEnableFunctions(
    WithPostgres, ApplicationTestCase
):
    postgres_schema = "myschema"
    postgres_enable_db_functions = "y"


class TestApplicationWithPostgresSchemaNoPublic(WithPostgres, ApplicationTestCase):
    postgres_dbname = "eventsourcing_nopublic"
    postgres_schema = "myschema"


class TestApplicationWithPostgresSchemaNoPublicEnableFunctions(
    WithPostgres, ApplicationTestCase
):
    postgres_dbname = "eventsourcing_nopublic"
    postgres_schema = "myschema"
    postgres_enable_db_functions = "y"


class TestExampleApplicationWithPostgres(WithPostgres, ExampleApplicationTestCase):
    pass


del ApplicationTestCase
del ExampleApplicationTestCase
del WithPostgres
