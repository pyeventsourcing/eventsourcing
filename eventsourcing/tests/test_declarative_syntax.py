from typing import cast
from unittest import TestCase

from eventsourcing.application import Application
from eventsourcing.declarative import aggregate, event
from eventsourcing.domain import Aggregate


@aggregate
class World:
    def __init__(self, name):
        self.name = name
        self.history = []

    def make_it_so(self, what):
        self._trigger_event(self.SomethingHappened, what=what)

    @event
    def _something_happened(self, what):
        self.history.append(what)

    def set_name(self, name):
        self._trigger_event(self.NameChanged, name=name)

    @event
    def _name_changed(self, name):
        self.name = name


class TestDeclarativeSyntax(TestCase):
    def test_aggregate_and_event(self):

        # Create a new world.
        world = World(name="Earth")

        # Check the aggregate.
        self.assertIsInstance(world, World)
        self.assertEqual(world.name, "Earth")
        self.assertEqual(world.history, [])

        # Make trucks so.
        world.make_it_so("Trucks")

        # Check the history.
        self.assertEqual(world.history, ["Trucks"])

        # Set the name.
        world.set_name("Mars")

        # Check the name has changed.
        self.assertEqual(world.name, "Mars")

        # Check the domain events were triggered.
        pending_events = world.collect_events()
        self.assertEqual(len(pending_events), 3)
        self.assertIsInstance(pending_events[0], World.Created)
        self.assertIsInstance(pending_events[1], World.SomethingHappened)
        self.assertIsInstance(pending_events[2], World.NameChanged)

    def test_with_application(self):

        # Construct application and aggregate.
        app = Application()
        world = World(name="Earth")
        world.make_it_so("Trucks")
        world.set_name("Mars")
        app.save(cast(Aggregate, world))

        # Check the recorded state at current version.
        copy = app.repository.get(world.id)
        self.assertIsInstance(copy, World)
        self.assertEqual(copy.name, "Mars")
        self.assertEqual(copy.history, ["Trucks"])

        # Check the recorded state at previous versions.
        copy = app.repository.get(world.id, version=1)
        self.assertIsInstance(copy, World)
        self.assertEqual(copy.name, "Earth")
        self.assertEqual(copy.history, [])

        copy = app.repository.get(world.id, version=2)
        self.assertIsInstance(copy, World)
        self.assertEqual(copy.history, ["Trucks"])
        self.assertEqual(copy.name, "Earth")

        copy = app.repository.get(world.id, version=3)
        self.assertIsInstance(copy, World)
        self.assertEqual(copy.history, ["Trucks"])
        self.assertEqual(copy.name, "Mars")
