from eventsourcing.application.simple import ApplicationWithConcreteInfrastructure
from eventsourcing.infrastructure.django.factory import DjangoInfrastructureFactory
from eventsourcing.infrastructure.django.utils import close_django_connection, setup_django


class DjangoApplicationMeta(type(ApplicationWithConcreteInfrastructure)):
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
        from eventsourcing.infrastructure.django.models import NotificationTrackingRecord
        return NotificationTrackingRecord


class DjangoApplication(ApplicationWithConcreteInfrastructure, metaclass=DjangoApplicationMeta):

    infrastructure_factory_class = DjangoInfrastructureFactory
    tracking_record_class = None

    def __init__(self, tracking_record_class=None, *args, **kwargs):
        _tracking_record_class = tracking_record_class \
                                     or self.tracking_record_class \
                                     or type(self).tracking_record_class

        if isinstance(_tracking_record_class, str):
            raise Exception(_tracking_record_class)
        self.tracking_record_class = _tracking_record_class
        super(DjangoApplication, self).__init__(*args, **kwargs)

    def construct_infrastructure(self, *args, **kwargs):
        super(DjangoApplication, self).construct_infrastructure(
            tracking_record_class=self.tracking_record_class,
            *args, **kwargs
        )

    @classmethod
    def reset_connection_after_forking(cls):
        """
        Resets database connection after forking.
        """
        close_django_connection()
        setup_django()
