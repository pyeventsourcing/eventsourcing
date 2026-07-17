from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.application import Application
from eventsourcing.dataclasses.immutable import DataclassDecision
from eventsourcing.dataclasses.transcoder import DataclassTranscoder

if TYPE_CHECKING:
    from eventsourcing.persistence import Transcoder


class DataclassApplication(Application[DataclassDecision]):
    def construct_transcoder(self) -> Transcoder[DataclassDecision]:
        return DataclassTranscoder()
