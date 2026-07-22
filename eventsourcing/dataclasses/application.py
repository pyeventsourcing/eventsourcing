from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.application import AggregatesApplication
from eventsourcing.dataclasses.immutable import TDataclassDecision
from eventsourcing.dataclasses.transcoder import DataclassTranscoder
from eventsourcing.dcb.application import DCBApplication

if TYPE_CHECKING:
    from eventsourcing.persistence import Transcoder


class DataclassAggregatesApplication(AggregatesApplication[TDataclassDecision]):
    def construct_transcoder(self) -> Transcoder[TDataclassDecision]:
        return DataclassTranscoder()


class DataclassDCBApplication(DCBApplication[TDataclassDecision]):
    def construct_transcoder(self) -> Transcoder[TDataclassDecision]:
        return DataclassTranscoder()
