class EventSourcingError(Exception):
    pass


class TopicResolutionError(EventSourcingError):
    pass


class ConcurrencyError(EventSourcingError):
    pass


class AppendError(EventSourcingError):
    pass