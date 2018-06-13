from eventsourcing.application.command import CommandProcess
from eventsourcing.application.process import ProcessApplication
from eventsourcing.application.simple import SimpleApplication

from eventsourcing.infrastructure.sqlalchemy.factory import SQLAlchemyInfrastructureFactory
from eventsourcing.infrastructure.sqlalchemy.records import EntitySnapshotRecord, StoredEventRecord


class ApplicationWithSQLAlchemy(SimpleApplication):
    infrastructure_factory_class = SQLAlchemyInfrastructureFactory
    stored_event_record_class = StoredEventRecord
    snapshot_record_class = EntitySnapshotRecord

    def __init__(self, uri=None, pool_size=5, session=None, **kwargs):
        self.uri = uri
        self.pool_size = pool_size
        self.session = session
        super(ApplicationWithSQLAlchemy, self).__init__(**kwargs)

    def setup_infrastructure(self, *args, **kwargs):
        super(ApplicationWithSQLAlchemy, self).setup_infrastructure(
            session=self.session, uri=self.uri, pool_size=self.pool_size,
            *args, **kwargs
        )
        if self.datastore and self.session is None:
            self.session = self.datastore.session


class ProcessApplicationWithSQLAlchemy(ApplicationWithSQLAlchemy, ProcessApplication):
    pass


class CommandProcessWithSQLAlchemy(ApplicationWithSQLAlchemy, CommandProcess):
    pass


class SimpleApplication(ApplicationWithSQLAlchemy):
    """
    Shorter name for ApplicationWithSQLAlchemy.
    """


class ProcessApplication(ProcessApplicationWithSQLAlchemy):
    """Shorter name for ProcessApplicationWithSQLAlchemy."""


class CommandProcess(CommandProcessWithSQLAlchemy):
    """Shorter name for CommandProcessWithSQLAlchemy."""
