from eventsourcing.application.process import ProcessApplication
from eventsourcing.domain.model.command import Command


class CommandProcess(ProcessApplication):
    persist_event_type = Command.Event
