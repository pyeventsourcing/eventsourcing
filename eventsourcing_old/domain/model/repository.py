from abc import abstractmethod
from typing import Generic, Optional
from uuid import UUID

from eventsourcing.domain.model.events import AbstractSnapshot
from eventsourcing.whitehead import TEntity, TEvent


class AbstractEntityRepository(Generic[TEntity, TEvent]):
    @abstractmethod
    def __getitem__(self, entity_id: UUID) -> TEntity:
        """
        Returns entity for given ID.

        Raises ``RepositoryKeyError`` when entity not found.
        """

    @abstractmethod
    def __contains__(self, entity_id: UUID) -> bool:
        """
        Returns True or False, according to whether or not entity exists.
        """

    @abstractmethod
    def get_entity(
        self, entity_id: UUID, at: Optional[int] = None
    ) -> Optional[TEntity]:
        """
        Returns entity for given ID.

        Returns None when entity not found.
        """

    @abstractmethod
    def take_snapshot(
        self, entity_id: UUID, lt: Optional[int] = None, lte: Optional[int] = None
    ) -> Optional[AbstractSnapshot]:
        """
        Takes snapshot of entity state, using stored events.
        """
