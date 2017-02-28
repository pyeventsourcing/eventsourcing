from abc import ABCMeta, abstractmethod

import six


class DatastoreStrategy(six.with_metaclass(ABCMeta)):
    def __init__(self, settings, tables):
        self.settings = settings
        self.tables = tables

    @abstractmethod
    def setup_connection(self):
        """Sets up a connection to a datastore."""

    @abstractmethod
    def drop_connection(self):
        """Drops connection to a datastore."""

    @abstractmethod
    def setup_tables(self):
        """Sets up tables used to store events."""

    @abstractmethod
    def drop_tables(self):
        """Drops tables used to store events."""
