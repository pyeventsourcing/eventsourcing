from eventsourcing.domain.model.array import AbstractArrayRepository, AbstractBigArrayRepository, Array, BigArray
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


class ArrayRepository(EventSourcedRepository, AbstractArrayRepository):
    def __getitem__(self, array_id):
        """
        Returns sequence for given ID.
        """
        return Array(array_id=array_id, repo=self)


class BigArrayRepository(ArrayRepository, AbstractBigArrayRepository):
    subrepo_class = ArrayRepository

    def __init__(self, *args, **kwargs):
        super(BigArrayRepository, self).__init__(*args, **kwargs)
        self._subrepo = self.subrepo_class(
            event_store=self.event_store,
            sequence_size=self.array_size,
        )

    @property
    def subrepo(self):
        return self._subrepo

    def __getitem__(self, array_id):
        """
        Returns sequence for given ID.
        """
        return BigArray(array_id=array_id, repo=self, subrepo=self.subrepo)
