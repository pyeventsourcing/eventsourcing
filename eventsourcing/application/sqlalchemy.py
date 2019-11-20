from typing import Any, Optional

from eventsourcing.application.simple import ApplicationWithConcreteInfrastructure
from eventsourcing.infrastructure.sqlalchemy.factory import (
    SQLAlchemyInfrastructureFactory,
)
from eventsourcing.infrastructure.sqlalchemy.records import (
    EntitySnapshotRecord,
    StoredEventRecord,
)


class SQLAlchemyApplication(ApplicationWithConcreteInfrastructure):
    infrastructure_factory_class = SQLAlchemyInfrastructureFactory
    stored_event_record_class = StoredEventRecord
    snapshot_record_class = EntitySnapshotRecord
    is_constructed_with_session = True
    tracking_record_class = None

    def __init__(
        self,
        uri: Optional[str] = None,
        session: Optional[Any] = None,
        tracking_record_class: Any = None,
        **kwargs: Any
    ):
        self.uri = uri
        self.session = session
        self.tracking_record_class = (
            tracking_record_class or type(self).tracking_record_class
        )
        super(SQLAlchemyApplication, self).__init__(**kwargs)

    def construct_infrastructure(self, *args: Any, **kwargs: Any) -> None:
        super(SQLAlchemyApplication, self).construct_infrastructure(
            session=self.session,
            uri=self.uri,
            tracking_record_class=self.tracking_record_class,
            *args,
            **kwargs
        )
        if self.datastore and self.session is None:
            self.session = self.datastore.session
