from typing import Any, Dict, Optional
from uuid import UUID

from eventsourcing.domain.model.events import (
    AbstractSnapshot,
    EventWithOriginatorID,
    EventWithOriginatorVersion,
    EventWithTimestamp,
)
from eventsourcing.utils.topic import reconstruct_object, resolve_topic
from eventsourcing.whitehead import TEntity


class Snapshot(
    EventWithTimestamp,
    EventWithOriginatorVersion,
    EventWithOriginatorID,
    AbstractSnapshot,
):
    def __init__(
        self,
        originator_id: UUID,
        originator_version: int,
        topic: str,
        state: Optional[Dict],
    ):
        super(Snapshot, self).__init__(
            originator_id=originator_id,
            originator_version=originator_version,
            topic=topic,
            state=state,
        )

    @property
    def topic(self) -> str:
        """
        Path to the class of the snapshotted entity.
        """
        return self.__dict__["topic"]

    @property
    def state(self) -> Dict[str, Any]:
        """
        State of the snapshotted entity.
        """
        return self.__dict__["state"]

    def __mutate__(self, obj: Optional[TEntity]) -> Optional[TEntity]:
        if self.state is not None:
            entity_class = resolve_topic(self.topic)
            return reconstruct_object(entity_class, self.state)
