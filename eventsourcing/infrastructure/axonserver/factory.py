from typing import Any, NamedTuple, Optional, Type

from eventsourcing.infrastructure.axonserver.datastore import (
    AxonDatastore,
    AxonSettings,
)
from eventsourcing.infrastructure.axonserver.manager import AxonRecordManager
from eventsourcing.infrastructure.base import AbstractRecordManager
from eventsourcing.infrastructure.datastore import AbstractDatastore
from eventsourcing.infrastructure.factory import InfrastructureFactory


class AxonInfrastructureFactory(InfrastructureFactory):
    """
    Infrastructure factory for Axon infrastructure.
    """

    record_manager_class = AxonRecordManager
    integer_sequenced_record_class = None
    timestamp_sequenced_record_class = None
    snapshot_record_class = None
    tracking_record_class = None

    def __init__(
        self, axon_client=None, uri: Optional[str] = None, *args: Any, **kwargs: Any
    ):
        super(AxonInfrastructureFactory, self).__init__(*args, **kwargs)
        self.axon_client = axon_client
        self.uri = uri

    def construct_integer_sequenced_record_manager(
        self, **kwargs: Any
    ) -> AbstractRecordManager:
        """
        Constructs Axon record manager.

        :return: An Axon record manager.
        :rtype: AxonRecordManager
        """
        return super(
            AxonInfrastructureFactory, self
        ).construct_integer_sequenced_record_manager(**kwargs)

    def construct_record_manager(
        self,
        record_class: Optional[type],
        sequenced_item_class: Optional[Type[NamedTuple]] = None,
        **kwargs: Any
    ) -> AbstractRecordManager:
        """
        Constructs Axon record manager.

        :return: An Axon record manager.
        :rtype: AxonRecordManager
        """
        return super(AxonInfrastructureFactory, self).construct_record_manager(
            record_class,
            sequenced_item_class=sequenced_item_class,
            axon_client=self.axon_client,
            **kwargs
        )

    def construct_datastore(self) -> Optional[AbstractDatastore]:
        """
        Constructs Axon datastore.

        :rtype: AxonDatastore
        """
        datastore = AxonDatastore(settings=AxonSettings(uri=self.uri))
        assert datastore.axon_client
        if self.axon_client is None:
            self.axon_client = datastore.axon_client
        return datastore
