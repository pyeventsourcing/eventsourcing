from typing import Any

from eventsourcing.application.simple import ApplicationWithConcreteInfrastructure
from eventsourcing.infrastructure.django.factory import DjangoInfrastructureFactory
from eventsourcing.infrastructure.django.utils import (
    close_django_connection,
    setup_django,
)


class DjangoApplication(ApplicationWithConcreteInfrastructure):
    infrastructure_factory_class = DjangoInfrastructureFactory

    def __init__(self, tracking_record_class: Any = None, *args: Any, **kwargs: Any):
        self._tracking_record_class = tracking_record_class
        super(DjangoApplication, self).__init__(*args, **kwargs)

    @property
    def stored_event_record_class(self) -> type:  # type: ignore
        # This is awkward, but need to avoid importing library Django models.
        from eventsourcing.infrastructure.django.models import StoredEventRecord

        return StoredEventRecord

    @property
    def snapshot_record_class(cls) -> type:  # type: ignore
        # This is awkward, but need to avoid importing library Django models.
        from eventsourcing.infrastructure.django.models import EntitySnapshotRecord

        return EntitySnapshotRecord

    @property
    def tracking_record_class(cls) -> Any:
        from eventsourcing.infrastructure.django.models import (
            NotificationTrackingRecord,
        )

        return NotificationTrackingRecord

    def construct_infrastructure(self, *args: Any, **kwargs: Any) -> None:
        tracking_record_class = (
            self._tracking_record_class or self.tracking_record_class
        )
        super(DjangoApplication, self).construct_infrastructure(
            tracking_record_class=tracking_record_class, *args, **kwargs
        )

    @classmethod
    def reset_connection_after_forking(cls) -> None:
        """
        Resets database connection after forking.
        """
        close_django_connection()
        setup_django()
