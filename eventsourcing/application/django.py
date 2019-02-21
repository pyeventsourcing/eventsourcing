from eventsourcing.application.simple import ApplicationWithConcreteInfrastructure
from eventsourcing.infrastructure.django.manager import DjangoRecordManager
from eventsourcing.infrastructure.django.models import EntitySnapshotRecord, StoredEventRecord
from eventsourcing.infrastructure.django.utils import close_django_connection, setup_django


class DjangoApplication(ApplicationWithConcreteInfrastructure):
    record_manager_class = DjangoRecordManager
    stored_event_record_class = StoredEventRecord
    snapshot_record_class = EntitySnapshotRecord

    @classmethod
    def reset_connection_after_forking(cls):
        """
        Resets database connection after forking.
        """
        close_django_connection()
        setup_django()
