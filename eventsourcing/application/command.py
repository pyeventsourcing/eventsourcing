from typing import Optional, Type

from eventsourcing.application.process import ProcessApplication
from eventsourcing.domain.model.command import Command
from eventsourcing.domain.model.entity import DomainEntity


class CommandProcess(ProcessApplication):
    persist_event_type = Command.Event
