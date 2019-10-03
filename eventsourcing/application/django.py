from eventsourcing.application.simple import ApplicationWithConcreteInfrastructure
from eventsourcing.infrastructure.django.factory import DjangoInfrastructureFactory
from eventsourcing.infrastructure.django.utils import (
    close_django_connection,
    setup_django,
)


class DjangoApplication(ApplicationWithConcreteInfrastructure):
    infrastructure_factory_class = DjangoInfrastructureFactory

    def __init__(self, tracking_record_class=None, *args, **kwargs):
        self._tracking_record_class = tracking_record_class
        super(DjangoApplication, self).__init__(*args, **kwargs)

    @property
    def stored_event_record_class(cls):
        from eventsourcing.infrastructure.django.models import StoredEventRecord

        return StoredEventRecord

    @property
    def snapshot_record_class(cls):
        from eventsourcing.infrastructure.django.models import EntitySnapshotRecord

        return EntitySnapshotRecord

    @property
    def tracking_record_class(cls):
        from eventsourcing.infrastructure.django.models import (
            NotificationTrackingRecord,
        )

        return NotificationTrackingRecord

    def construct_infrastructure(self, *args, **kwargs):
        tracking_record_class = (
            self._tracking_record_class or self.tracking_record_class
        )
        super(DjangoApplication, self).construct_infrastructure(
            tracking_record_class=tracking_record_class, *args, **kwargs
        )

    @classmethod
    def reset_connection_after_forking(cls):
        """
        Resets database connection after forking.
        """
        close_django_connection()
        setup_django()
