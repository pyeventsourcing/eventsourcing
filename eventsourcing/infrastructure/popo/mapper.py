from typing import Any, Dict, Tuple, Type

from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
from eventsourcing.utils.topic import get_topic, resolve_topic
from eventsourcing.whitehead import TEvent


class SequencedItemMapperForPopo(SequencedItemMapper):
    def get_event_class_and_attrs(
        self, topic: str, state: bytes
    ) -> Tuple[Type[TEvent], Dict]:
        return resolve_topic(topic), state  # type: ignore

    def get_item_topic_and_state(
        self, domain_event_class: type, event_attrs: Dict[str, Any]
    ) -> Tuple[str, bytes]:
        return get_topic(domain_event_class), event_attrs  # type: ignore
