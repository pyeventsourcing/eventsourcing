from typing import cast
from unittest import TestCase
from uuid import UUID

from eventsourcing.application import Application
from eventsourcing.declarative import aggregate, event
from eventsourcing.domain import Aggregate


class TestDeclarativeSyntax(TestCase):
    def test_world1_aggregate_and_event(self):

        # Create a new world.
        world = World1(name="Earth")

        # Check the aggregate.
        self.assertIsInstance(world, World1)
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
        self.assertIsInstance(pending_events[0], World1.Created)
        self.assertIsInstance(pending_events[1], World1.SomethingHappened)
        self.assertIsInstance(pending_events[2], World1.NameChanged)

    def test_world1_with_application(self):

        # Construct application and aggregate.
        app = Application()
        world = World1(name="Earth")
        world.make_it_so("Trucks")
        world.set_name("Mars")
        app.save(cast(Aggregate, world))

        # Check the recorded state at current version.
        copy = app.repository.get(world.id)
        self.assertIsInstance(copy, World1)
        self.assertEqual(copy.name, "Mars")
        self.assertEqual(copy.history, ["Trucks"])

        # Check the recorded state at previous versions.
        copy = app.repository.get(world.id, version=1)
        self.assertIsInstance(copy, World1)
        self.assertEqual(copy.name, "Earth")
        self.assertEqual(copy.history, [])

        copy = app.repository.get(world.id, version=2)
        self.assertIsInstance(copy, World1)
        self.assertEqual(copy.history, ["Trucks"])
        self.assertEqual(copy.name, "Earth")

        copy = app.repository.get(world.id, version=3)
        self.assertIsInstance(copy, World1)
        self.assertEqual(copy.history, ["Trucks"])
        self.assertEqual(copy.name, "Mars")

    def test_world2_aggregate_and_event(self):

        # Create a new world.
        world = World2(name="Earth")

        # Check the aggregate.
        self.assertIsInstance(world, World2)
        self.assertEqual(world.name, "Earth")
        self.assertEqual(world.history, [])

        # Make trucks so.
        world.make_it_so(what="Trucks")

        # Check the history.
        self.assertEqual(world.history, ["Trucks"])

        # Set the name.
        world.name = "Mars"

        # Check the name has changed.
        self.assertEqual(world.name, "Mars")

        # Check the domain events were triggered.
        pending_events = world.collect_events()
        self.assertEqual(len(pending_events), 3)
        self.assertIsInstance(pending_events[0], World2.Created)
        self.assertIsInstance(pending_events[1], World2.SomethingHappened)
        self.assertIsInstance(pending_events[2], World2.NameChanged)

    def test_world2_aggregate_and_event_args_not_kwargs(self):

        # Create a new world.
        world = World2(name="Earth")

        # Check the aggregate.
        self.assertIsInstance(world, World2)
        self.assertEqual(world.name, "Earth")
        self.assertEqual(world.history, [])

        # Make trucks so.
        world.make_it_so("Trucks")

        # Check the history.
        self.assertEqual(world.history, ["Trucks"])

        # Set the name.
        world.name = "Mars"

        # Check the name has changed.
        self.assertEqual(world.name, "Mars")

        # Check the domain events were triggered.
        pending_events = world.collect_events()
        self.assertEqual(len(pending_events), 3)
        self.assertIsInstance(pending_events[0], World2.Created)
        self.assertIsInstance(pending_events[1], World2.SomethingHappened)
        self.assertIsInstance(pending_events[2], World2.NameChanged)

    def test_world2_with_application(self):

        # Construct application and aggregate.
        app = Application()
        world = World2(name="Earth")
        world.make_it_so(what="Trucks")
        world.name = "Mars"
        app.save(cast(Aggregate, world))

        # Check the recorded state at current version.
        copy = app.repository.get(world.id)
        self.assertIsInstance(copy, World2)
        self.assertEqual(copy.name, "Mars")
        self.assertEqual(copy.history, ["Trucks"])

        # Check the recorded state at previous versions.
        copy = app.repository.get(world.id, version=1)
        self.assertIsInstance(copy, World2)
        self.assertEqual(copy.name, "Earth")
        self.assertEqual(copy.history, [])

        copy = app.repository.get(world.id, version=2)
        self.assertIsInstance(copy, World2)
        self.assertEqual(copy.history, ["Trucks"])
        self.assertEqual(copy.name, "Earth")

        copy = app.repository.get(world.id, version=3)
        self.assertIsInstance(copy, World2)
        self.assertEqual(copy.history, ["Trucks"])
        self.assertEqual(copy.name, "Mars")

    def test_world3_set_name(self):

        # Create a new world.
        world = World3(name="Earth")
        self.assertEqual(world.name, "Earth")
        world.name = "Mars"
        self.assertEqual(world.name, "Mars")
        self.assertIsInstance(world._pending_events[-1], World3.NameChanged)

    # def test_world4_positional_only_params(self):
    #     # Create a new world.
    #     world = World4()
    #     world.make_it_so("Trucks")
    #     self.assertEqual(world.history[-1], "Trucks")
    #     self.assertIsInstance(world._pending_events[-1],  World4.SomethingHappened)

    def test_missing_init(self):
        aggregate = AggregateWithoutInit()
        self.assertIsInstance(aggregate.id, UUID)
        aggregate.set_name("name")
        self.assertEqual(aggregate.name, "name")
        pending = aggregate.collect_events()
        self.assertEqual(len(pending), 2)
        self.assertIsInstance(pending[-1], AggregateWithoutInit.NameChanged)


@aggregate
class World1:
    def __init__(self, name):
        self.name = name
        self.history = []

    def make_it_so(self, what):
        self._trigger_event(self.SomethingHappened, what=what)

    @event
    def _something_happened(self, what):
        self.history.append(what)

    def set_name(self, name):
        self._name_changed.trigger(name)

    @event
    def _name_changed(self, name):
        self.name = name


# Todo: Put method signature in event decorator, so that args can be mapped to names.
# Todo: Maybe allow __init__ to call super, in which case don't redefine __init__.


@aggregate
class World2(Aggregate):
    def __init__(self, name):
        self._name = name
        self.history = []

    @event("SomethingHappened")
    def make_it_so(self, what):
        self.history.append(what)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self.name_changed(name=name)

    @event
    def name_changed(self, name):
        self._name = name


@aggregate
class World3:
    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

    @name.setter
    @event("NameChanged")
    def name(self, name):
        self._name = name


# Todo: Move to >3.7 module and selectively import.
# @aggregate
# class World4(Aggregate):
#
#     def __init__(self):
#         self.history = []
#
#     @event("SomethingHappened")
#     def make_it_so(self, what, /):
#         self.history.append(what)


@aggregate
class AggregateWithoutInit:
    @event("NameChanged")
    def set_name(self, name):
        self.name = name
