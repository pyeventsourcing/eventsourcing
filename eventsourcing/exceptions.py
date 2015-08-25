class EventSourcingError(Exception):
    pass


class TopicResolutionError(EventSourcingError):
    pass
