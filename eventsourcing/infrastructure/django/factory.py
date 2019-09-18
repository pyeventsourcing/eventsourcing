from abc import ABCMeta

from eventsourcing.infrastructure.factory import InfrastructureFactory


class DjangoInfrastructureFactoryMeta(ABCMeta):
    @property
    def record_manager_class(self):
        from eventsourcing.infrastructure.django.manager import DjangoRecordManager
        return DjangoRecordManager

    @property
    def integer_sequenced_record_class(self):
        from eventsourcing.infrastructure.django.models import IntegerSequencedRecord
        return IntegerSequencedRecord

    @property
    def timestamp_sequenced_record_class(self):
        from eventsourcing.infrastructure.django.models import TimestampSequencedRecord
        return TimestampSequencedRecord

    @property
    def snapshot_record_class(self):
        from eventsourcing.infrastructure.django.models import SnapshotRecord
        return SnapshotRecord

    @property
    def tracking_record_class(self):
        from eventsourcing.infrastructure.django.models import NotificationTrackingRecord
        return NotificationTrackingRecord


class DjangoInfrastructureFactory(InfrastructureFactory, metaclass=DjangoInfrastructureFactoryMeta):
    """
    Infrastructure factory for Django.
    """
    def __init__(self, tracking_record_class=None, *args, **kwargs):
        super(DjangoInfrastructureFactory, self).__init__(*args, **kwargs)
        self.tracking_record_class = tracking_record_class or type(self).tracking_record_class

    def construct_record_manager(self, *args, **kwargs):
        """
        Constructs Django record manager.
        :param args:
        :param kwargs:
        :return: A Django record manager.
        :rtype: DjangoRecordManager
        """
        return super(DjangoInfrastructureFactory, self).construct_record_manager(
            tracking_record_class=type(self).tracking_record_class,
            *args, **kwargs
        )
