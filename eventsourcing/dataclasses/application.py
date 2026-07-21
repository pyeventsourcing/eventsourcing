from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.application import AggregatesApplication
from eventsourcing.dataclasses.immutable import DataclassDecision
from eventsourcing.dataclasses.transcoder import DataclassTranscoder
from eventsourcing.dcb.application import DCBApplication

if TYPE_CHECKING:
    from eventsourcing.persistence import Transcoder


class DataclassAggregatesApplication(AggregatesApplication[DataclassDecision]):
    def construct_transcoder(self) -> Transcoder[DataclassDecision]:
        return DataclassTranscoder()


class DataclassDCBApplication(DCBApplication[DataclassDecision]):
    def construct_transcoder(self) -> Transcoder[DataclassDecision]:
        return DataclassTranscoder()
