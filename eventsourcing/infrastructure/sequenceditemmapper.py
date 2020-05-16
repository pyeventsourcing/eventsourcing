from abc import ABC, abstractmethod
from json import JSONDecodeError
from typing import Any, Dict, Generic, NamedTuple, Optional, Tuple, Type

from eventsourcing.infrastructure.sequenceditem import (
    SequencedItem,
    SequencedItemFieldNames,
)
from eventsourcing.utils.cipher.aes import AESCipher
from eventsourcing.utils.topic import get_topic, reconstruct_object, resolve_topic
from eventsourcing.utils.transcoding import ObjectJSONDecoder, ObjectJSONEncoder
from eventsourcing.whitehead import TEvent


class AbstractSequencedItemMapper(Generic[TEvent], ABC):
    def __init__(self, **kwargs: Any):
        """
        Initialises mapper.
        """

    @abstractmethod
    def item_from_event(self, domain_event: TEvent) -> NamedTuple:
        """
        Constructs and returns a sequenced item for given domain event.
        """

    @abstractmethod
    def event_from_item(self, sequenced_item: NamedTuple) -> TEvent:
        """
        Constructs and returns a domain event for given sequenced item.
        """

    @abstractmethod
    def json_dumps(self, o: object) -> bytes:
        """
        Encodes given object as JSON.
        """

    @abstractmethod
    def json_loads(self, s: str) -> object:
        """
        Decodes given JSON as object.
        """

    @abstractmethod
    def event_from_topic_and_state(self, topic: str, state: bytes) -> TEvent:
        """
        Resolves topic to an event class, decodes state, and constructs an event.
        """


class SequencedItemMapper(AbstractSequencedItemMapper[TEvent]):
    """
    Uses JSON to transcode domain events.
    """

    def __init__(
        self,
        sequenced_item_class: Optional[Type[NamedTuple]] = None,
        sequence_id_attr_name: Optional[str] = None,
        position_attr_name: Optional[str] = None,
        json_encoder_class: Optional[Type[ObjectJSONEncoder]] = None,
        sort_keys: bool = False,
        json_decoder_class: Optional[Type[ObjectJSONDecoder]] = None,
        cipher: Optional[AESCipher] = None,
        compressor: Any = None,
        other_attr_names: Tuple[str, ...] = (),
    ):
        if sequenced_item_class is not None:
            self.sequenced_item_class = sequenced_item_class
        else:
            self.sequenced_item_class = SequencedItem  # type: ignore
        self.json_encoder_class = json_encoder_class or ObjectJSONEncoder
        self.json_encoder = self.json_encoder_class(sort_keys=sort_keys)
        self.json_decoder_class = json_decoder_class or ObjectJSONDecoder
        self.json_decoder = self.json_decoder_class()
        self.cipher = cipher
        self.compressor = compressor
        self.field_names = SequencedItemFieldNames(self.sequenced_item_class)
        self.sequence_id_attr_name = (
            sequence_id_attr_name or self.field_names.sequence_id
        )
        self.position_attr_name = position_attr_name or self.field_names.position
        self.other_attr_names = other_attr_names or self.field_names.other_names

    def item_from_event(self, domain_event: TEvent) -> NamedTuple:
        """
        Constructs a sequenced item from a domain event.
        """
        item_args = self.construct_item_args(domain_event)
        return self.construct_sequenced_item(item_args)

    def construct_item_args(self, domain_event: TEvent) -> Tuple:
        """
        Constructs attributes of a sequenced item from the given domain event.
        """
        # Get the sequence ID.
        sequence_id = domain_event.__dict__[self.sequence_id_attr_name]

        # Get the position in the sequence.
        position = getattr(domain_event, self.position_attr_name, None)

        # Get topic and data.
        topic, state = self.get_item_topic_and_state(
            domain_event.__class__, domain_event.__dict__
        )

        # Get the 'other' args.
        # - these are meant to be derivative of the other attributes,
        #   to populate database fields, and shouldn't affect the hash.
        other_args = tuple(
            (getattr(domain_event, name) for name in self.other_attr_names)
        )

        return (sequence_id, position, topic, state) + other_args

    def get_item_topic_and_state(
        self, domain_event_class: type, event_attrs: Dict[str, Any]
    ) -> Tuple[str, bytes]:
        # Get the topic from the event attrs, otherwise from the class.
        topic = get_topic(domain_event_class)

        # Serialise the event attributes.
        statebytes = self.json_dumps(event_attrs)

        # Compress plaintext bytes.
        if self.compressor:
            # Zlib reduces length by about 25% to 50%.
            statebytes = self.compressor.compress(statebytes)

        # Encrypt serialised state.
        if self.cipher:
            # Increases length by about 10%.
            statebytes = self.cipher.encrypt(statebytes)

        return topic, statebytes

    def json_dumps(self, o: object) -> bytes:
        return self.json_encoder.encode(o)

    def construct_sequenced_item(self, item_args: Tuple) -> NamedTuple:
        return self.sequenced_item_class(*item_args)

    def event_from_item(self, sequenced_item: NamedTuple) -> TEvent:
        """
        Reconstructs domain event from stored event topic and
        event attrs. Used in the event store when getting domain events.
        """
        assert isinstance(sequenced_item, self.sequenced_item_class), (
            self.sequenced_item_class,
            type(sequenced_item),
        )

        # Get the topic and state.
        topic = getattr(sequenced_item, self.field_names.topic)
        state = getattr(sequenced_item, self.field_names.state)

        return self.event_from_topic_and_state(topic, state)

    def event_from_topic_and_state(self, topic: str, state: bytes) -> TEvent:
        domain_event_class, event_attrs = self.get_event_class_and_attrs(topic, state)

        # Reconstruct domain event object.
        return reconstruct_object(domain_event_class, event_attrs)

    def get_event_class_and_attrs(
        self, topic: str, state: bytes
    ) -> Tuple[Type[TEvent], Dict]:
        # Resolve topic to event class.
        domain_event_class: Type[TEvent] = resolve_topic(topic)

        # Decrypt and decompress state.
        if self.cipher:
            state = self.cipher.decrypt(state)

        # Decompress plaintext bytes.
        if self.compressor:
            state = self.compressor.decompress(state)

        # Decode unicode bytes.
        statestr = state.decode("utf8")

        # Deserialize JSON.
        event_attrs: Dict = self.json_loads(statestr)

        # Return instance class and attribute values.
        return domain_event_class, event_attrs

    def json_loads(self, s: str) -> Dict:
        try:
            return self.json_decoder.decode(s)
        except JSONDecodeError:
            raise ValueError("Couldn't load JSON string: {}".format(s))
