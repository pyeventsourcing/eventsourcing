from typing import Any, Optional

from eventsourcing.application.simple import ApplicationWithConcreteInfrastructure
from eventsourcing.infrastructure.factory import InfrastructureFactory
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
    tracking_record_class: Any = None

    def __init__(
        self,
        uri: Optional[str] = None,
        session: Optional[Any] = None,
        tracking_record_class: Any = None,
        **kwargs: Any
    ):
        self.uri = uri
        self._session = session
        self.tracking_record_class = (
            tracking_record_class or type(self).tracking_record_class
        )
        super(SQLAlchemyApplication, self).__init__(**kwargs)

    @property
    def session(self) -> Optional[Any]:
        return self._session

    def construct_infrastructure(self, *args: Any, **kwargs: Any) -> None:
        super(SQLAlchemyApplication, self).construct_infrastructure(
            session=self.session,
            uri=self.uri,
            tracking_record_class=self.tracking_record_class,
            *args,
            **kwargs
        )

    def construct_infrastructure_factory(
        self, *args: Any, **kwargs: Any
    ) -> InfrastructureFactory:
        return super(SQLAlchemyApplication, self).construct_infrastructure_factory(
            *args, **kwargs
        )

    def construct_datastore(self) -> None:
        super(SQLAlchemyApplication, self).construct_datastore()
        assert self._datastore
        assert self._datastore.session
        if self._session is None:
            self._session = self._datastore.session
