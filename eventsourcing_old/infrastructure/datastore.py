from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, TypeVar


class DatastoreSettings(object):
    """
    Settings for Datastore.
    """


TDatastoreSettings = TypeVar("TDatastoreSettings", bound=DatastoreSettings)


class AbstractDatastore(ABC, Generic[TDatastoreSettings]):
    can_drop_tables = True
    """
    Datastores hold stored event records, used by a record manager.
    """

    def __init__(self, settings: TDatastoreSettings):
        self.settings: TDatastoreSettings = settings

    @property
    def session(self) -> Optional[Any]:
        return None

    @abstractmethod
    def setup_connection(self) -> None:
        """Sets up a connection to a datastore."""

    @abstractmethod
    def close_connection(self) -> None:
        """Drops connection to a datastore."""

    @abstractmethod
    def setup_tables(self) -> None:
        """Sets up tables used to store events."""

    @abstractmethod
    def setup_table(self, table: Any) -> None:
        """Sets up given table."""

    @abstractmethod
    def drop_tables(self) -> None:
        """Drops tables used to store events."""

    @abstractmethod
    def drop_table(self, table: Any) -> None:
        """Drops given table."""

    @abstractmethod
    def truncate_tables(self) -> None:
        """Truncates tables used to store events."""


class DatastoreError(Exception):
    pass


class DatastoreConnectionError(DatastoreError):
    pass


class DatastoreTableError(DatastoreError):
    pass
