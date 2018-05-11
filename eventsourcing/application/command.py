from eventsourcing.application.process import ProcessApplication
from eventsourcing.application.simple import SimpleApplicationWithSQLAlchemy
from eventsourcing.domain.model.command import Command


class CommandProcess(ProcessApplication):
    persist_event_type = Command.Event


class CommandProcessWithSQLAlchemy(CommandProcess, SimpleApplicationWithSQLAlchemy):
    pass
