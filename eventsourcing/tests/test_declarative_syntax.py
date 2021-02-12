import inspect
from copy import copy
from dataclasses import dataclass
from typing import Dict, Type, cast
from unittest import TestCase
from uuid import uuid4

from eventsourcing.application import Application
from eventsourcing.domain import Aggregate

aggregate_classes: Dict["aggregate", Aggregate] = {}
event_classes: Dict["str", Aggregate.Event] = {}


def aggregate(cls) -> Type[Aggregate]:
    new_cls = type(cls.__name__, (cls, Aggregate), {})
    new_cls.__qualname__ = cls.__qualname__
    new_cls.__module__ = cls.__module__
    new_cls.__doc__ = cls.__doc__

    created_cls = Aggregate.Created

    for name in dir(cls):
        attribute = getattr(cls, name)
        if isinstance(attribute, event):
            # Prepare the subsequent aggregate events.
            original_method = attribute.original_method
            event_cls_name = event_name_from_method_name(name)
            event_cls_qualname = ".".join([cls.__qualname__, event_cls_name])

            method_signature = inspect.signature(original_method)
            annotations = {}
            for param_name in method_signature.parameters:
                if param_name == "self":
                    continue
                annotations[param_name] = "typing.Any"

            event_cls_dict = {"__annotations__": annotations}

            event_cls = type(event_cls_name, (Aggregate.Event,), event_cls_dict)

            event_cls = dataclass(event_cls, frozen=True)
            event_cls.__qualname__ = event_cls_qualname
            event_cls.__module__ = cls.__module__

            def apply(self, aggregate):
                event_obj_dict = copy(self.__dict__)
                event_obj_dict.pop("originator_id")
                event_obj_dict.pop("originator_version")
                event_obj_dict.pop("timestamp")
                self.original_method(aggregate, **event_obj_dict)

            event_cls.apply = apply
            event_cls.original_method = staticmethod(original_method)
            fullqualname = ".".join((cls.__module__, event_cls.__qualname__))
            event_classes[fullqualname] = event_cls
            setattr(new_cls, event_cls_name, event_cls)
        elif name == "__init__":
            # Prepare the "created" event.
            method_signature = inspect.signature(attribute)
            annotations = {}
            for param_name in method_signature.parameters:
                if param_name == "self":
                    continue
                annotations[param_name] = "typing.Any"

            event_cls_dict = {"__annotations__": annotations}

            created_cls = type("Created", (Aggregate.Created,), event_cls_dict)
            created_cls.__qualname__ = ".".join([cls.__qualname__, "Created"])
            created_cls.__module__ = cls.__module__

            new_cls.Created = created_cls

            created_cls = dataclass(created_cls, frozen=True)

    original_init = new_cls.__init__

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            return  # Python calls me again...
        base_kwargs = {}
        base_kwargs["id"] = kwargs.pop("id")
        base_kwargs["version"] = kwargs.pop("version")
        base_kwargs["timestamp"] = kwargs.pop("timestamp")
        Aggregate.__init__(self, **base_kwargs)
        original_init(self, **kwargs)

    cls.__init__ = __init__

    def __new__(cls, **kwargs):
        return cls._create(event_class=created_cls, id=uuid4(), **kwargs)

    new_cls.__new__ = __new__

    return cast(Type[Aggregate], new_cls)


def event_name_from_method_name(name):
    return "".join([s.capitalize() for s in name.split("_")])


class event:
    def __init__(self, original_method):
        self.original_method = original_method


def get_event_class_from_original_method(method):
    event_name = event_name_from_method_name(method.__name__)
    qualname_prefix = method.__qualname__[: -len(method.__name__) - 1]
    module_name = method.__module__
    fullqualname = ".".join([module_name, qualname_prefix, event_name])
    return event_classes[fullqualname]


@aggregate
class World:
    def __init__(self, name):
        self.name = name
        self.history = []

    def make_it_so(self, what):
        self._trigger_event(self.SomethingHappened, what=what)

    @event
    def something_happened(self, what):
        self.history.append(what)

    def set_name(self, name):
        self._trigger_event(self.NameChanged, name=name)

    @event
    def name_changed(self, name):
        self.name = name


class TestDeclarativeSyntax(TestCase):
    def test_aggregate_and_event(self):
        world = World(name="Earth")
        self.assertIsInstance(world, World)
        self.assertIsInstance(world.history, list)
        self.assertEqual(world.history, [])
        self.assertEqual(world.name, "Earth")

        world.make_it_so("Trucks")
        self.assertEqual(world.history, ["Trucks"])

        world.set_name("Mars")
        self.assertEqual(world.name, "Mars")

        pending_events = world.collect_events()
        self.assertEqual(len(pending_events), 3)
        self.assertIsInstance(pending_events[0], World.Created)
        self.assertIsInstance(pending_events[1], World.SomethingHappened)
        self.assertIsInstance(pending_events[2], World.NameChanged)

    def test_with_application(self):
        world = World(name="Earth")
        world.make_it_so("Trucks")

        app = Application()
        app.save(cast(Aggregate, world))
        copy = app.repository.get(world.id)
        self.assertIsInstance(copy, World)
        self.assertEqual(copy.name, "Earth")
        self.assertEqual(copy.history, ["Trucks"])
