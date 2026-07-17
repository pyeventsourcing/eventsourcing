from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.application import Application
from eventsourcing.pydantic.immutable import PydanticDecision
from eventsourcing.pydantic.transcoder import PydanticTranscoder

if TYPE_CHECKING:
    from eventsourcing.persistence import Transcoder


class PydanticApplication(Application[PydanticDecision]):
    def construct_transcoder(self) -> Transcoder[PydanticDecision]:
        return PydanticTranscoder()
