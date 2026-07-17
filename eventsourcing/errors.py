from __future__ import annotations


class EventSourcingError(Exception):
    """Base exception class."""


class TranscodingNotRegisteredError(EventSourcingError, TypeError):
    """Raised when a transcoding isn't registered with JSONTranscoder."""


class MapperDeserialisationError(EventSourcingError, ValueError):
    """Raised when deserialization fails in a Mapper."""


class RecordConflictError(EventSourcingError):
    """Legacy exception, replaced with IntegrityError."""


class PersistenceError(EventSourcingError):
    """The base class of the other exceptions in this module.

    Exception class names follow https://www.python.org/dev/peps/pep-0249/#exceptions
    """


class InterfaceError(PersistenceError):
    """Exception raised for errors that are related to the database
    interface rather than the database itself.
    """


class DatabaseError(PersistenceError):
    """Exception raised for errors that are related to the database."""


class DataError(DatabaseError):
    """Exception raised for errors that are due to problems with the
    processed data like division by zero, numeric value out of range, etc.
    """


class OperationalError(DatabaseError):
    """Exception raised for errors that are related to the database's
    operation and not necessarily under the control of the programmer,
    e.g. an unexpected disconnect occurs, the data source name is not
    found, a transaction could not be processed, a memory allocation
    error occurred during processing, etc.
    """


class NotSupportedError(DatabaseError):
    """Exception raised in case a method or database API was used
    which is not supported by the database, e.g. calling the
    rollback() method on a connection that does not support
    transaction or has transactions turned off.
    """


class WaitInterruptedError(PersistenceError):
    """Raised when waiting for a tracking record is interrupted."""


class InfrastructureFactoryError(EventSourcingError):
    """Raised when an infrastructure factory cannot be created."""


class ConnectionPoolClosedError(EventSourcingError):
    """Raised when using a connection pool that is already closed."""


class ConnectionNotFromPoolError(EventSourcingError):
    """Raised when putting a connection in the wrong pool."""


class ConnectionUnavailableError(OperationalError, TimeoutError):
    """Raised when a request to get a connection from a
    connection pool times out.
    """


class ProgrammingError(EventSourcingError):
    """Exception class for programming errors."""
