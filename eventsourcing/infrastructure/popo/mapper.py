from typing import Tuple, Type, Dict, Any

from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.whitehead import TEvent


class SequencedItemMapperForPopo(SequencedItemMapper):
    def get_event_class_and_attrs(
        self, topic: str, state: bytes
    ) -> Tuple[Type[TEvent], Dict]:
        return topic, state  # type: ignore

    def get_item_topic_and_state(
        self, domain_event_class: type, event_attrs: Dict[str, Any]
    ) -> Tuple[str, bytes]:
        return domain_event_class, event_attrs  # type: ignore
