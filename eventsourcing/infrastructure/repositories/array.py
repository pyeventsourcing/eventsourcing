from typing import Any

from eventsourcing.domain.model.array import (
    AbstractArrayRepository,
    AbstractBigArrayRepository,
)
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


class ArrayRepository(AbstractArrayRepository, EventSourcedRepository):
    pass


class BigArrayRepository(AbstractBigArrayRepository, EventSourcedRepository):
    subrepo_class = ArrayRepository

    def __init__(self, array_size: int = 10000, *args: Any, **kwargs: Any):
        super(BigArrayRepository, self).__init__(*args, **kwargs)
        self._subrepo = self.subrepo_class(
            event_store=self.event_store, array_size=array_size
        )

    @property
    def subrepo(self) -> ArrayRepository:
        return self._subrepo
