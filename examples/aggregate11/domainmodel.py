from __future__ import annotations

import uuid

from eventsourcing.decorator import triggers
from eventsourcing.pydantic import Aggregate


class Dog(Aggregate):
    INITIAL_VERSION = 0

    @staticmethod
    def create_id() -> str:
        return "dog-" + str(uuid.uuid4())

    @triggers("Registered")
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: list[str] = []

    @triggers("TrickAdded")
    def add_trick(self, trick: str) -> None:
        self.tricks.append(trick)
