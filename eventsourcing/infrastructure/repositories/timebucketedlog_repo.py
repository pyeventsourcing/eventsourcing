from eventsourcing.domain.model.timebucketedlog import Timebucketedlog, TimebucketedlogRepository
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


class TimebucketedlogRepo(EventSourcedRepository, TimebucketedlogRepository):
    """
    Event sourced repository for the Example domain model entity.
    """
    def __init__(self, *args, **kwargs):
        super(TimebucketedlogRepo, self).__init__(
            mutator=Timebucketedlog._mutate,
            *args, **kwargs
        )
