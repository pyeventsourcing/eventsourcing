import unittest

from eventsourcing.infrastructure.stored_event_repos.with_python_objects import PythonObjectsStoredEventRepository


class PythonObjectsTestCase(unittest.TestCase):

    @property
    def stored_event_repo(self):
        try:
            return self._stored_event_repo
        except AttributeError:
            stored_event_repo = PythonObjectsStoredEventRepository()
            self._stored_event_repo = stored_event_repo
            return stored_event_repo