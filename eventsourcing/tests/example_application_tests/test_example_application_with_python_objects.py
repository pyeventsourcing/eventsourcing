from eventsourcing.tests.example_application_tests.base import ExampleApplicationTestCase
from eventsourcing.tests.stored_event_repository_tests.test_python_objects_stored_event_repository import \
    PythonObjectsRepoTestCase


class TestExampleApplicationWithPythonObjects(PythonObjectsRepoTestCase, ExampleApplicationTestCase):
    pass


class TestExampleApplicationWithPythonObjectsUseCache(PythonObjectsRepoTestCase, ExampleApplicationTestCase):
    def construct_application(self):
        app = super(TestExampleApplicationWithPythonObjectsUseCache, self).construct_application()
        app.example_repo._use_cache = True
        return app
