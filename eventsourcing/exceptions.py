class EventSourcingError(Exception):
    pass


class TopicResolutionError(EventSourcingError):
    pass


class ConcurrencyError(EventSourcingError):
    pass
