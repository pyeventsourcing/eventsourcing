from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.application import AggregatesApplication
from eventsourcing.dcb.application import DCBApplication
from eventsourcing.pydantic.immutable import TPydanticDecision
from eventsourcing.pydantic.transcoder import PydanticTranscoder

if TYPE_CHECKING:
    from eventsourcing.persistence import Transcoder


class PydanticAggregatesApplication(AggregatesApplication[TPydanticDecision]):
    def construct_transcoder(self) -> Transcoder[TPydanticDecision]:
        return PydanticTranscoder()


class PydanticDCBApplication(DCBApplication[TPydanticDecision]):
    def construct_transcoder(self) -> Transcoder[TPydanticDecision]:
        return PydanticTranscoder()
