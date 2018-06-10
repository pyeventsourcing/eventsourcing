from eventsourcing.application.command import CommandProcess
from eventsourcing.application.process import ProcessApplication
from eventsourcing.application.simple import AbstractSimpleApplication


class SimpleApplicationWithSQLAlchemy(AbstractSimpleApplication):
    def __init__(self, uri=None, pool_size=5, session=None, *args, **kwargs):
        self.uri = uri
        self.pool_size = pool_size
        self.session = session
        from eventsourcing.infrastructure.sqlalchemy.factory import SQLAlchemyInfrastructureFactory
        from eventsourcing.infrastructure.sqlalchemy.records import EntitySnapshotRecord, StoredEventRecord
        super(SimpleApplicationWithSQLAlchemy, self).__init__(
            infrastructure_factory_class=SQLAlchemyInfrastructureFactory,
            stored_event_record_class=StoredEventRecord,
            snapshot_record_class=EntitySnapshotRecord,
            *args, **kwargs)

    def setup_infrastructure(self, *args, **kwargs):
        super(SimpleApplicationWithSQLAlchemy, self).setup_infrastructure(session=self.session, uri=self.uri,
                                                                          pool_size=self.pool_size, *args, **kwargs)
        if self.datastore and self.session is None:
            self.session = self.datastore.session


class SimpleApplication(SimpleApplicationWithSQLAlchemy):
    """
    Shorter name for SimpleApplicationWithSQLAlchemy.
    """


class CommandProcessWithSQLAlchemy(CommandProcess, SimpleApplicationWithSQLAlchemy):
    pass


class ProcessApplicationWithSQLAlchemy(ProcessApplication, SimpleApplicationWithSQLAlchemy):
    pass
