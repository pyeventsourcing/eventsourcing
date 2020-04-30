from uuid import uuid4

from axonclient.client import DEFAULT_LOCAL_AXONSERVER_URI, AxonClient, AxonEvent

from eventsourcing.infrastructure.axonserver.datastore import (
    AxonDatastore,
    AxonSettings,
)
from eventsourcing.infrastructure.axonserver.factory import AxonInfrastructureFactory
from eventsourcing.tests.datastore_tests import base


class AxonDatastoreTestCase(base.AbstractDatastoreTestCase):
    """
    Base class for test cases that use an Axon datastore.
    """

    infrastructure_factory_class = AxonInfrastructureFactory

    def construct_datastore(self):
        return AxonDatastore(settings=AxonSettings())

    def create_factory_kwargs(self):
        kwargs = super(AxonDatastoreTestCase, self).create_factory_kwargs()
        kwargs["axon_client"] = AxonClient(self.datastore.settings.uri)
        return kwargs


class TestAxonDatastore(AxonDatastoreTestCase, base.DatastoreTestCase):
    """
    Test case for Axon datastore.
    """

    def list_records(self):
        datastore = self.datastore
        assert isinstance(datastore, AxonDatastore)
        assert isinstance(datastore.axon_client, AxonClient)
        query = datastore.axon_client.list_events()
        return list(query)

    def create_record(self):
        datastore = self.datastore
        assert isinstance(datastore, AxonDatastore)
        assert isinstance(datastore.axon_client, AxonClient)
        datastore.axon_client.append_event(
            AxonEvent(
                message_identifier=str(uuid4()),
                aggregate_identifier=uuid4().hex,
                aggregate_sequence_number=0,
                aggregate_type="AggregateRoot",
                timestamp=0,
                payload_type="a",
                payload_revision="1",
                payload_data=b"",
                snapshot=False,
                meta_data={},
            )
        )
