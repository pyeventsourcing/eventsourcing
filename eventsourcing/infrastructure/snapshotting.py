from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Optional
from uuid import UUID

from eventsourcing.domain.model.entity import TVersionedEntity
from eventsourcing.domain.model.snapshot import Snapshot
from eventsourcing.infrastructure.base import (
    AbstractEventStore,
    AbstractRecordManager,
    AbstractSnapshop,
)
from eventsourcing.infrastructure.sequenceditemmapper import reconstruct_object
from eventsourcing.utils.topic import get_topic, resolve_topic


class AbstractSnapshotStrategy(ABC):
    @abstractmethod
    def get_snapshot(
        self, entity_id: UUID, lt: Optional[int] = None, lte: Optional[int] = None
    ) -> Optional[AbstractSnapshop]:
        """
        Gets the last snapshot for entity, optionally until a particular version number.

        :rtype: Snapshot
        """

    @abstractmethod
    def take_snapshot(
        self, entity_id: UUID, entity: object, last_event_version: int
    ) -> Snapshot:
        """
        Takes a snapshot of entity, using given ID, state and version number.
        """


class EventSourcedSnapshotStrategy(AbstractSnapshotStrategy):
    """Snapshot strategy that uses an event sourced snapshot.
    """

    def __init__(
        self,
        snapshot_store: AbstractEventStore[AbstractSnapshop, AbstractRecordManager],
    ):
        self.snapshot_store = snapshot_store

    def get_snapshot(
        self, entity_id: UUID, lt: Optional[int] = None, lte: Optional[int] = None
    ) -> Optional[AbstractSnapshop]:
        """
        Gets the last snapshot for entity, optionally until a particular version number.

        :rtype: Snapshot
        """
        snapshots = self.snapshot_store.list_events(
            entity_id, lt=lt, lte=lte, limit=1, is_ascending=False
        )
        snapshot = None
        if len(snapshots) == 1:
            snapshot = snapshots[0]
        return snapshot

    # Todo: Rename as create_snapshot?
    def take_snapshot(
        self, entity_id: UUID, entity: object, last_event_version: int
    ) -> Snapshot:
        """
        Creates a Snapshot from the given state, and appends it
        to the snapshot store.

        :rtype: Snapshot
        """

        # Create the snapshot.
        snapshot = Snapshot(
            originator_id=entity_id,
            originator_version=last_event_version,
            topic=get_topic(entity.__class__),
            state=None if entity is None else deepcopy(entity.__dict__),
        )

        self.snapshot_store.store_events([snapshot])

        # Return the snapshot.
        return snapshot


def entity_from_snapshot(snapshot: AbstractSnapshop) -> Optional[TVersionedEntity]:
    """
    Reconstructs domain entity from given snapshot.
    """
    assert isinstance(snapshot, AbstractSnapshop), type(snapshot)
    if snapshot.state is not None:
        entity_class = resolve_topic(snapshot.topic)
        return reconstruct_object(entity_class, snapshot.state)
