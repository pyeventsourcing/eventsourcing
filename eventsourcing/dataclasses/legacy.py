from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, cast, override
from uuid import UUID

from eventsourcing.dataclasses import Decision, Transcoder
from eventsourcing.errors import TranscodingNotRegisteredError


class Transcoding(ABC):
    """Abstract base class for custom transcodings."""

    type: type
    name: str

    @abstractmethod
    def encode(self, obj: Any) -> Any:
        """Encodes given object."""

    @abstractmethod
    def decode(self, data: Any) -> Any:
        """Decodes encoded object."""


class LegacyJSONTranscoder(Transcoder):
    """Extensible transcoder that uses the Python :mod:`json` module."""

    def __init__(self) -> None:
        super().__init__()
        self.types: dict[type, Transcoding] = {}
        self.names: dict[str, Transcoding] = {}
        # Need to reconstruct this because simply setting object_hook is not effective.
        self.decoder = json.JSONDecoder(object_hook=self._decode_obj)

    def register(self, transcoding: Transcoding) -> None:
        """Registers given transcoding with the transcoder."""
        self.types[transcoding.type] = transcoding
        self.names[transcoding.name] = transcoding

    @override
    def encode(self, decision: Decision) -> bytes:
        """Encodes given object as a bytes array."""
        return self.encoder.encode(decision.as_dict()).encode("utf8")

    @override
    def decode(self, data: bytes, decision_class: type[Decision]) -> Decision:
        """Decodes bytes array as previously encoded object."""
        return decision_class(**self.decoder.decode(data.decode("utf8")))

    @override
    def _dump_obj(self, obj: Any) -> dict[str, Any]:
        try:
            transcoding = self.types[type(obj)]
        except KeyError:
            msg = (
                f"Object of type {type(obj)} is not "
                "serializable. Please define and register "
                "a custom transcoding for this type."
            )
            raise TranscodingNotRegisteredError(msg) from None
        else:
            return {
                "_type_": transcoding.name,
                "_data_": transcoding.encode(obj),
            }

    def _decode_obj(self, d: dict[str, Any]) -> Any:
        if len(d) == 2:
            try:
                _type_ = d["_type_"]
            except KeyError:
                return d
            else:
                try:
                    _data_ = d["_data_"]
                except KeyError:
                    return d
                else:
                    try:
                        transcoding = self.names[cast("str", _type_)]
                    except KeyError as e:
                        msg = (
                            f"Data serialized with name '{cast('str', _type_)}' is not "
                            "deserializable. Please register a "
                            "custom transcoding for this type."
                        )
                        raise TranscodingNotRegisteredError(msg) from e
                    else:
                        return transcoding.decode(_data_)
        else:
            return d


class UUIDAsHex(Transcoding):
    """Transcoding that represents :class:`UUID` objects as hex values."""

    type = UUID
    name = "uuid_hex"

    @override
    def encode(self, obj: UUID) -> str:
        return obj.hex

    @override
    def decode(self, data: str) -> UUID:
        assert isinstance(data, str)
        return UUID(data)


class DecimalAsStr(Transcoding):
    """Transcoding that represents :class:`Decimal` objects as strings."""

    type = Decimal
    name = "decimal_str"

    @override
    def encode(self, obj: Decimal) -> str:
        return str(obj)

    @override
    def decode(self, data: str) -> Decimal:
        return Decimal(data)


class DatetimeAsISO(Transcoding):
    """Transcoding that represents :class:`datetime` objects as ISO strings."""

    type = datetime
    name = "datetime_iso"

    @override
    def encode(self, obj: datetime) -> str:
        return obj.isoformat()

    @override
    def decode(self, data: str) -> datetime:
        assert isinstance(data, str)
        return datetime.fromisoformat(data)
