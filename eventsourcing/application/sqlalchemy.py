from eventsourcing.application import command, process, simple, snapshotting

from eventsourcing.infrastructure.sqlalchemy.factory import SQLAlchemyInfrastructureFactory
from eventsourcing.infrastructure.sqlalchemy.records import EntitySnapshotRecord, StoredEventRecord


class SimpleApplication(simple.SimpleApplication):
    infrastructure_factory_class = SQLAlchemyInfrastructureFactory
    stored_event_record_class = StoredEventRecord
    snapshot_record_class = EntitySnapshotRecord
    is_constructed_with_session = True

    def __init__(self, uri=None, pool_size=5, session=None, **kwargs):
        self.uri = uri
        self.pool_size = pool_size
        self.session = session
        super(SimpleApplication, self).__init__(**kwargs)

    def setup_infrastructure(self, *args, **kwargs):
        super(SimpleApplication, self).setup_infrastructure(
            session=self.session, uri=self.uri, pool_size=self.pool_size,
            *args, **kwargs
        )
        if self.datastore and self.session is None:
            self.session = self.datastore.session


class ApplicationWithSnapshotting(snapshotting.ApplicationWithSnapshotting, SimpleApplication):
    pass


class ProcessApplication(process.ProcessApplication, SimpleApplication):
    pass


class ProcessApplicationWithSnapshotting(process.ProcessApplicationWithSnapshotting, SimpleApplication):
    pass


class CommandProcess(command.CommandProcess, SimpleApplication):
    pass
