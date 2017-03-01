from unittest.case import TestCase

from eventsourcing.application.example.with_pythonobjects import ExampleApplicationWithPythonObjects


class App(ExampleApplicationWithPythonObjects):
    persist_events = False


class TestApplication(TestCase):

    def test_persistance_disabled(self):
        app = App()
        self.assertIsNone(app.persistence_subscriber)
        app.close()
