from abc import ABC, abstractmethod


class DatastoreSettings(object):
    """Base class for settings for database connection used by a stored event repository."""


class Datastore(ABC):
    def __init__(self, settings):
        # assert isinstance(settings, DatastoreSettings), settings
        self.settings = settings

    @abstractmethod
    def setup_connection(self):
        """Sets up a connection to a datastore."""

    @abstractmethod
    def close_connection(self):
        """Drops connection to a datastore."""

    @abstractmethod
    def setup_tables(self):
        """Sets up tables used to store events."""

    @abstractmethod
    def drop_tables(self):
        """Drops tables used to store events."""

    @abstractmethod
    def truncate_tables(self):
        """Truncates tables used to store events."""


class DatastoreError(Exception):
    pass


class DatastoreConnectionError(DatastoreError):
    pass


class DatastoreTableError(DatastoreError):
    pass
