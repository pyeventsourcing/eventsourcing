from uuid import uuid1

from cassandra import InvalidRequest
from cassandra.cluster import NoHostAvailable
from cassandra.cqlengine import CQLEngineException

from eventsourcing.infrastructure.datastore.base import DatastoreConnectionError, DatastoreTableError
from eventsourcing.infrastructure.datastore.cassandra import CassandraDatastoreStrategy, CassandraSettings
from eventsourcing.infrastructure.stored_event_repos.with_cassandra import CqlStoredEvent
from eventsourcing.tests.datastore_tests.base import DatastoreStrategyTestCase


class TestCassandraDatastoreStrategy(DatastoreStrategyTestCase):
    def setup_datastore_strategy(self):
        self.strategy = CassandraDatastoreStrategy(
            settings=CassandraSettings(
                default_keyspace='eventsourcing_testing'
            ),
            tables=(CqlStoredEvent,),
        )

    def list_records(self):
        try:
            return list(CqlStoredEvent.objects.all())
        except (CQLEngineException, NoHostAvailable) as e:
            raise DatastoreConnectionError(e)
        except InvalidRequest as e:
            raise DatastoreTableError(e)

    def create_record(self):
        record = CqlStoredEvent(n='entity1', v=uuid1(), t='topic', a='{}')
        try:
            record.save()
        except (CQLEngineException, NoHostAvailable) as e:
            raise DatastoreConnectionError(e)
        except InvalidRequest as e:
            raise DatastoreTableError(e)
        return record
