from __future__ import annotations

from eventsourcing.application import Application
from eventsourcing.domain import TAggregateID
from eventsourcing.msgspec.mapper import MsgspecMapper
from eventsourcing.persistence import Mapper, NullTranscoder


class MsgspecApplication(Application[TAggregateID]):
    def construct_mapper(self) -> Mapper[TAggregateID]:
        return MsgspecMapper(
            transcoder=NullTranscoder(),
            cipher=self.factory.cipher(),
            compressor=self.factory.compressor(),
        )
