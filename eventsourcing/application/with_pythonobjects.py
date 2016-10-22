from eventsourcing.application.base import EventSourcingApplication
from eventsourcing.infrastructure.stored_events.in_python_objects import PythonObjectsStoredEventRepository


class EventSourcingWithPythonObjects(EventSourcingApplication):

    def create_stored_event_repo(self, *args, **kwargs):
        return PythonObjectsStoredEventRepository(*args, **kwargs)
