import inspect
from copy import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Type
from unittest import TestCase
from uuid import UUID, uuid4

from eventsourcing.domain import Aggregate, TAggregate

aggregate_classes: Dict["aggregate", Aggregate] = {}
event_classes: Dict["str", Aggregate.Event] = {}


def aggregate(cls) -> Type[TAggregate]:
    new_cls = type(cls.__name__, (cls, Aggregate), {})
    new_cls.__qualname__ = cls.__qualname__
    new_cls.__module__ = cls.__module__
    new_cls.__doc__ = cls.__doc__

    for name in dir(cls):
        attribute = getattr(cls, name)
        if isinstance(attribute, event):
            event_cls_name = event_name_from_method_name(name)
            event_cls_qualname = ".".join([cls.__qualname__, event_cls_name])

            method_signature = inspect.signature(attribute.original_method)
            annotations = {}
            for param_name in method_signature.parameters:
                if param_name == "self":
                    continue
                annotations[param_name] = "typing.Any"

            event_cls_dict = {
                "__annotations__": annotations
            }

            event_cls = type(event_cls_name, (Aggregate.Event,), event_cls_dict)


            event_cls = dataclass(event_cls, frozen=True)
            event_cls.__qualname__ = event_cls_qualname
            event_cls.__module__ = cls.__module__
            def apply(self, aggregate):
                event_obj_dict = copy(self.__dict__)
                event_obj_dict.pop("originator_id")
                event_obj_dict.pop("originator_version")
                event_obj_dict.pop("timestamp")
                attribute.original_method(aggregate, **event_obj_dict)
            event_cls.apply = apply
            fullqualname = ".".join((cls.__module__, event_cls.__qualname__))
            event_classes[fullqualname] = event_cls
            setattr(new_cls, event_cls_name, event_cls)

    def __init__(self, **kwargs):
        base_kwargs = {}
        base_kwargs["id"] = kwargs.pop("id")
        base_kwargs["version"] = kwargs.pop("version")
        base_kwargs["timestamp"] = kwargs.pop("timestamp")
        Aggregate.__init__(self, **base_kwargs)
        cls.__init__(self, **kwargs)

    new_cls.__init__ = __init__

    return new_cls


def event_name_from_method_name(name):
    return "".join([s.capitalize() for s in name.split('_')])


class event:
    def __init__(self, original_method):
        self.original_method = original_method

    @classmethod
    def trigger(self, method: "event", **kwargs):
        m = method.original_method
        event_class = get_event_class_from_original_method(m)
        raise Exception(m.__self__)


def get_event_class_from_original_method(method):
    event_name = event_name_from_method_name(method.__name__)
    qualname_prefix = method.__qualname__[:-len(method.__name__)-1]
    module_name = method.__module__
    fullqualname = ".".join([module_name, qualname_prefix, event_name])
    return event_classes[fullqualname]


@aggregate
class World:
    def __init__(self, name):
        self.name = name
        self.history = []

    @dataclass(frozen=True)
    class Created(Aggregate.Created):
        name: str

    @classmethod
    def create(cls, name):
        return cls._create(cls.Created, id=uuid4(), name=name)

    def make_it_so(self, what):
        self._trigger_event(self.SomethingHappened, what=what)
        # event.trigger(self.something_happened, what=what)

    @event
    def something_happened(self, what):
        self.history.append(what)


class TestDeclarativeSyntax(TestCase):

    def test_aggregate_and_event(self):
        world = World.create(name="Earth")
        self.assertIsInstance(world, World)
        self.assertIsInstance(world.history, list)
        self.assertEqual(world.history, [])
        self.assertEqual(world.name, "Earth")

        world.make_it_so("Trucks")
        self.assertEqual(world.history, ["Trucks"])

        pending_events = world.collect_events()
        self.assertEqual(len(pending_events), 2)
        self.assertIsInstance(pending_events[0], World.Created)
        self.assertIsInstance(pending_events[1], World.SomethingHappened)

