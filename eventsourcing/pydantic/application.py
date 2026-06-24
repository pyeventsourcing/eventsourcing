from __future__ import annotations

from eventsourcing.application import Application
from eventsourcing.domain import TAggregateID
from eventsourcing.persistence import Mapper, NullTranscoder
from eventsourcing.pydantic.mapper import PydanticMapper


class PydanticApplication(Application[TAggregateID]):
    def construct_mapper(self) -> Mapper[TAggregateID]:
        return PydanticMapper(
            transcoder=NullTranscoder(),
            cipher=self.factory.cipher(),
            compressor=self.factory.compressor(),
        )
