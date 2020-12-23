from abc import abstractmethod
from typing import Type, TypeVar

from eventsourcing.system import System

A = TypeVar("A")


class AbstractRunner:
    def __init__(self, system: System):
        self.system = system
        self.is_started = False

    @abstractmethod
    def start(self) -> None:
        if self.is_started:
            raise self.AlreadyStarted()
        self.is_started = True

    class AlreadyStarted(Exception):
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def get(self, cls: Type[A]) -> A:
        pass
