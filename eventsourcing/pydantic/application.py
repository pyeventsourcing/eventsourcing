from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.application import AggregatesApplication
from eventsourcing.dcb.application import DCBApplication
from eventsourcing.pydantic.immutable import PydanticDecision
from eventsourcing.pydantic.transcoder import PydanticTranscoder

if TYPE_CHECKING:
    from eventsourcing.persistence import Transcoder


class PydanticAggregatesApplication(AggregatesApplication[PydanticDecision]):
    def construct_transcoder(self) -> Transcoder[PydanticDecision]:
        return PydanticTranscoder()


class PydanticDCBApplication(DCBApplication[PydanticDecision]):
    def construct_transcoder(self) -> Transcoder[PydanticDecision]:
        return PydanticTranscoder()
