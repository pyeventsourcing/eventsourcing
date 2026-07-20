from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from eventsourcing.dataclasses.immutable import DataclassDecision
from eventsourcing.persistence import Transcoder


class DataclassTranscoder(Transcoder[DataclassDecision]):
    def __init__(self) -> None:
        self.encoder = json.JSONEncoder(
            default=self._dump_obj,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        self.decoder = json.JSONDecoder()

    def encode(self, decision: DataclassDecision) -> bytes:
        return self.encoder.encode(decision).encode("utf8")

    def decode(
        self, data: bytes, decision_class: type[DataclassDecision]
    ) -> DataclassDecision:
        return decision_class(**(json.loads(data)))

    def _dump_obj(self, obj: Any) -> Any:
        # Half-hearted attempt to dump values into JSON-encodable types.
        # If this isn't good enough, use pydantic or msgspec

        # 1. Handle collections JSON doesn't know about
        if isinstance(obj, (set, frozenset)):
            return list(obj)

        # 2. Handle specific built-in types
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)

        # 3. Handle dataclasses specifically
        if dataclasses.is_dataclass(obj):
            # We use __dict__ rather than dataclasses.asdict(obj) here.
            # This keeps it a shallow dictionary, allowing the JSONEncoder
            # to properly loop back into _dump_obj for nested UUIDs/dates!
            return obj.__dict__

        # 4. Fallback for any other custom classes
        try:
            return obj.__dict__
        except AttributeError:
            msg = f"Can't dump {type(obj)} objects"
            raise TypeError(msg) from None
