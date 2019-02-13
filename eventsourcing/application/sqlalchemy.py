from eventsourcing.application.simple import SimpleApplication
from eventsourcing.infrastructure.sqlalchemy.factory import SQLAlchemyInfrastructureFactory
from eventsourcing.infrastructure.sqlalchemy.records import EntitySnapshotRecord, StoredEventRecord


class SQLAlchemyApplication(SimpleApplication):
    infrastructure_factory_class = SQLAlchemyInfrastructureFactory
    stored_event_record_class = StoredEventRecord
    snapshot_record_class = EntitySnapshotRecord
    is_constructed_with_session = True

    def __init__(self, uri=None, session=None, **kwargs):
        self.uri = uri
        self.session = session
        super(SQLAlchemyApplication, self).__init__(**kwargs)

    def setup_infrastructure(self, *args, **kwargs):
        super(SQLAlchemyApplication, self).setup_infrastructure(
            session=self.session, uri=self.uri, *args, **kwargs
        )
        if self.datastore and self.session is None:
            self.session = self.datastore.session
