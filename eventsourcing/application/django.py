from eventsourcing.application.simple import ApplicationWithConcreteInfrastructure
from eventsourcing.infrastructure.django.factory import DjangoInfrastructureFactory
from eventsourcing.infrastructure.django.utils import close_django_connection, setup_django


class DjangoMeta(type(ApplicationWithConcreteInfrastructure)):
    @property
    def record_manager_class(cls):
        from eventsourcing.infrastructure.django.manager import DjangoRecordManager
        return DjangoRecordManager

    @property
    def stored_event_record_class(cls):
        from eventsourcing.infrastructure.django.models import StoredEventRecord
        return StoredEventRecord

    @property
    def snapshot_record_class(cls):
        from eventsourcing.infrastructure.django.models import EntitySnapshotRecord
        return EntitySnapshotRecord


class DjangoApplication(ApplicationWithConcreteInfrastructure, metaclass=DjangoMeta):

    infrastructure_factory_class = DjangoInfrastructureFactory

    @classmethod
    def reset_connection_after_forking(cls):
        """
        Resets database connection after forking.
        """
        close_django_connection()
        setup_django()
