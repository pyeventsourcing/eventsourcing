from eventsourcing.application.command import CommandProcess
from eventsourcing.application.process import ProcessApplication
from eventsourcing.application.simple import SimpleApplication

from eventsourcing.infrastructure.django.manager import DjangoRecordManager
from eventsourcing.infrastructure.django.models import StoredEventRecord


class ApplicationWithDjango(SimpleApplication):
    record_manager_class = DjangoRecordManager
    stored_event_record_class = StoredEventRecord


class ProcessApplicationWithDjango(ApplicationWithDjango, ProcessApplication):
    pass


class CommandProcessWithDjango(ApplicationWithDjango, CommandProcess):
    pass


class SimpleApplication(ApplicationWithDjango):
    """Shorter name for ApplicationWithDjango."""


class ProcessApplication(ProcessApplicationWithDjango):
    """Shorter name for ProcessApplicationWithDjango."""


class CommandProcess(CommandProcessWithDjango):
    """Shorter name for CommandProcessWithDjango."""
