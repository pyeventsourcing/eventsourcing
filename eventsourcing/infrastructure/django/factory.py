from typing import Any, Optional

from eventsourcing.infrastructure.base import AbstractRecordManager
from eventsourcing.infrastructure.django.manager import DjangoRecordManager
from eventsourcing.infrastructure.factory import InfrastructureFactory


class DjangoInfrastructureFactory(InfrastructureFactory):
    """
    Infrastructure factory for Django.
    """

    record_manager_class = DjangoRecordManager
    tracking_record_class: Any = None

    def __init__(
        self, tracking_record_class: Optional[type] = None, *args: Any, **kwargs: Any
    ):
        super(DjangoInfrastructureFactory, self).__init__(*args, **kwargs)
        self._tracking_record_class = tracking_record_class

    @property
    def integer_sequenced_record_class(self) -> Optional[type]:  # type: ignore
        from eventsourcing.infrastructure.django.models import IntegerSequencedRecord

        return IntegerSequencedRecord

    @property
    def timestamp_sequenced_record_class(self) -> Optional[type]:  # type: ignore
        from eventsourcing.infrastructure.django.models import TimestampSequencedRecord

        return TimestampSequencedRecord

    @property
    def snapshot_record_class(self) -> Optional[type]:  # type: ignore
        from eventsourcing.infrastructure.django.models import SnapshotRecord

        return SnapshotRecord

    def construct_integer_sequenced_record_manager(
        self, **kwargs: Any
    ) -> AbstractRecordManager:
        """
        Constructs Django record manager.

        :return: A Django record manager.
        :rtype: DjangoRecordManager
        """
        tracking_record_class = (
            self._tracking_record_class or self.tracking_record_class
        )
        return super(
            DjangoInfrastructureFactory, self
        ).construct_integer_sequenced_record_manager(
            tracking_record_class=tracking_record_class, **kwargs
        )
