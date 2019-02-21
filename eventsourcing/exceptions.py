class EventSourcingError(Exception):
    """Base eventsourcing exception."""


class TopicResolutionError(EventSourcingError):
    """Raised when unable to resolve a topic to a Python class."""


class EntityVersionNotFound(EventSourcingError):
    """Raise when accessing an entity version that does not exist."""


class RecordConflictError(EventSourcingError):
    """Raised when database raises an integrity error."""


class PromptFailed(EventSourcingError):
    """Raised when prompt fails."""


class ConcurrencyError(RecordConflictError):
    """Raised when a record conflict is due to concurrency."""


class ConsistencyError(EventSourcingError):
    """Raised when applying an event stream to a versioned entity."""


class MismatchedOriginatorError(ConsistencyError):
    """Raised when applying an event to an inappropriate object."""


class OriginatorIDError(MismatchedOriginatorError):
    """Raised when applying an event to the wrong entity or aggregate."""


class OriginatorVersionError(MismatchedOriginatorError):
    """Raised when applying an event to the wrong version of an entity or aggregate."""


class MutatorRequiresTypeNotInstance(ConsistencyError):
    """Raised when mutator function received a class rather than an entity."""


class DataIntegrityError(ValueError, EventSourcingError):
    "Raised when a sequenced item is damaged (hash doesn't match data)"


class EventHashError(DataIntegrityError):
    "Raised when an event's seal hash doesn't match the hash of the state of the event."


class HeadHashError(DataIntegrityError, MismatchedOriginatorError):
    """Raised when applying an event with hash different from aggregate head."""


class EntityIsDiscarded(AssertionError):
    """Raised when access to a recently discarded entity object is attempted."""


class ProgrammingError(EventSourcingError):
    """Raised when programming errors are encountered."""


class RepositoryKeyError(KeyError, EventSourcingError):
    """Raised when using entity repository's dictionary like interface  to get an entity that does not exist."""


class ArrayIndexError(IndexError, EventSourcingError):
    """Raised when appending item to an array that is full."""


class DatasourceSettingsError(EventSourcingError):
    "Raised when an error is detected in settings for a datasource."


class OperationalError(EventSourcingError):
    "Raised when an operational error is encountered."


class TimeSequenceError(EventSourcingError):
    "Raised when a time sequence error occurs e.g. trying to save a timestamp that already exists."

class TrackingRecordNotFound(EventSourcingError):
    "Raised when a tracking record is not found."

class CausalDependencyFailed(EventSourcingError):
    "Raised when a causal dependency fails (after its tracking record not found)."

class EventRecordNotFound(EventSourcingError):
    "Raised when an event record is not found."
