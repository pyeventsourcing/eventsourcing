import os
from typing import Any, Optional

from axonclient.client import DEFAULT_LOCAL_AXONSERVER_URI, AxonClient

from eventsourcing.infrastructure.datastore import AbstractDatastore, DatastoreSettings


class AxonSettings(DatastoreSettings):
    def __init__(self, uri: Optional[str] = None):
        if uri is not None:
            self.uri = uri
        else:
            if "AXON_HOST" in os.environ:
                axon_db_uri = "{}:{}".format(
                    os.getenv("AXON_HOST"), os.getenv("AXON_PORT", "8124")
                )
            else:
                axon_db_uri = DEFAULT_LOCAL_AXONSERVER_URI
            self.uri = os.getenv("DB_URI", axon_db_uri)


class AxonDatastore(AbstractDatastore[AxonSettings]):
    can_drop_tables = False

    def __init__(self, settings: AxonSettings):
        super(AxonDatastore, self).__init__(settings=settings)
        self._axon_client: Optional[AxonClient] = None

    @property
    def axon_client(self):
        if self._axon_client is None:
            self.setup_connection()
        return self._axon_client

    def setup_connection(self) -> None:
        assert isinstance(self.settings, AxonSettings), self.settings
        if self._axon_client is None:
            self._axon_client = AxonClient(self.settings.uri)

    def close_connection(self):
        if self.axon_client is not None:
            self.axon_client.close_connection()

    def drop_table(self, table: Any) -> None:
        pass

    def drop_tables(self) -> None:
        pass

    def setup_table(self, table: Any) -> None:
        pass

    def setup_tables(self) -> None:
        pass

    def truncate_tables(self) -> None:
        pass
