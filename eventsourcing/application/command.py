from eventsourcing.application.process import Process
from eventsourcing.domain.model.command import Command


class CommandProcess(Process):
    persist_event_type = Command.Event
