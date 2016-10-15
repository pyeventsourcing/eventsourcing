class EventSourcingError(Exception):
    """
    Base class for explicit errors in the eventsourcing mechanism.
    """
    pass


class TopicResolutionError(EventSourcingError):
    """
    Error resolving a topic to a Python class.
    """
    pass


class EntityVersionDoesNotExist(EventSourcingError):
    """
    Error when accessing an entity version.
    """
    pass


class ConcurrencyError(EventSourcingError):
    """
    Error appending events to a versioned stream.
    """
    pass


class ConsistencyError(EventSourcingError):
    """
    Error applying an event stream to a versioned entity.
    """
    pass


class ProgrammingError(EventSourcingError):
    """
    Error when reaching conditions that must have arisen from programming errors.
    """
    pass

class RepositoryKeyError(KeyError, EventSourcingError):
    """
    Error when getting an entity from a repo.
    """
    pass
