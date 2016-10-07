from eventsourcing.application.example.with_pythonobjects import ExampleApplicationWithPythonObjects
import unittest


class App(ExampleApplicationWithPythonObjects):
    persist_events = False


class TestApplication(unittest.TestCase):

    def test_persistance_disabled(self):
        app = App()
        self.assertIsNone(app.persistence_subscriber)
        app.close()
