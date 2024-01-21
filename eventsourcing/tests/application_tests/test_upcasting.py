from __future__ import annotations

import os
from decimal import Decimal
from unittest import TestCase
from uuid import uuid4

from eventsourcing.application import Application
from eventsourcing.domain import Aggregate, AggregateEvent
from eventsourcing.utils import _topic_cache, get_topic


class TestUpcasting(TestCase):
    def setUp(self) -> None:
        os.environ["IS_SNAPSHOTTING_ENABLED"] = "y"

    def tearDown(self) -> None:
        del os.environ["IS_SNAPSHOTTING_ENABLED"]
        type(self).UpcastFixtureV1 = type(self).original_cls_v1
        type(self).UpcastFixtureV2 = type(self).original_cls_v2
        type(self).UpcastFixtureV3 = type(self).original_cls_v3

        topic_v1 = get_topic(self.UpcastFixtureV1)
        topic_v1_created = get_topic(self.UpcastFixtureV1.Created)

        if topic_v1 in _topic_cache:
            del _topic_cache[topic_v1]
        if topic_v1_created in _topic_cache:
            del _topic_cache[topic_v1_created]

        topic_v2 = get_topic(self.UpcastFixtureV2)
        topic_v2_created = get_topic(self.UpcastFixtureV2.Created)

        if topic_v2 in _topic_cache:
            del _topic_cache[topic_v2]
        if topic_v2_created in _topic_cache:
            del _topic_cache[topic_v2_created]

        topic_v3 = get_topic(self.UpcastFixtureV3)
        topic_v3_created = get_topic(self.UpcastFixtureV3.Created)

        if topic_v3 in _topic_cache:
            del _topic_cache[topic_v3]
        if topic_v3_created in _topic_cache:
            del _topic_cache[topic_v3_created]

    def test_upcast_created_event_from_v1(self):
        app = Application()

        topic_v1 = get_topic(self.UpcastFixtureV1)
        topic_v1_created = get_topic(self.UpcastFixtureV1.Created)

        aggregate = self.UpcastFixtureV1.create(a="text")
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, "text")
        self.assertFalse(hasattr(copy, "b"))
        self.assertFalse(hasattr(copy, "c"))
        self.assertFalse(hasattr(copy, "d"))

        # "Deploy" v2.
        del _topic_cache[topic_v1]
        del _topic_cache[topic_v1_created]
        type(self).UpcastFixtureV1 = self.UpcastFixtureV2

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 0)
        self.assertFalse(hasattr(copy, "c"))
        self.assertFalse(hasattr(copy, "d"))

        # "Deploy" v3.
        del _topic_cache[topic_v1]
        del _topic_cache[topic_v1_created]
        type(self).UpcastFixtureV1 = self.UpcastFixtureV3

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])

        # "Deploy" v4.
        del _topic_cache[topic_v1]
        type(self).UpcastFixtureV1 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])
        self.assertEqual(copy.d, None)

    def test_upcast_aggregate_snapshot_from_v1(self):
        app = Application()

        topic_v1 = get_topic(self.UpcastFixtureV1)

        aggregate = self.UpcastFixtureV1.create(a="text")
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, "text")
        self.assertFalse(hasattr(copy, "b"))
        self.assertFalse(hasattr(copy, "c"))
        self.assertFalse(hasattr(copy, "d"))

        app.take_snapshot(aggregate.id)

        # "Deploy" v2.
        del _topic_cache[topic_v1]
        type(self).UpcastFixtureV1 = self.UpcastFixtureV2

        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 0)
        self.assertFalse(hasattr(copy, "c"))
        self.assertFalse(hasattr(copy, "d"))

        # "Deploy" v3.
        del _topic_cache[topic_v1]
        type(self).UpcastFixtureV1 = self.UpcastFixtureV3

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])
        self.assertFalse(hasattr(copy, "d"))

        # "Deploy" v4.
        del _topic_cache[topic_v1]
        type(self).UpcastFixtureV1 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])
        self.assertEqual(copy.d, None)

    def test_upcast_created_event_from_v2(self):
        app = Application()

        topic_v2 = get_topic(self.UpcastFixtureV2)
        topic_v2_created = get_topic(self.UpcastFixtureV2.Created)

        aggregate = self.UpcastFixtureV2.create(aa="TEXT", b=1)
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertFalse(hasattr(copy, "c"))
        self.assertFalse(hasattr(copy, "d"))

        # "Deploy" v3.
        del _topic_cache[topic_v2]
        del _topic_cache[topic_v2_created]
        type(self).UpcastFixtureV2 = self.UpcastFixtureV3

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [])
        self.assertFalse(hasattr(copy, "d"))

        # "Deploy" v4.
        del _topic_cache[topic_v2]
        del _topic_cache[topic_v2_created]
        type(self).UpcastFixtureV2 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [])
        self.assertEqual(copy.d, None)

    def test_upcast_aggregate_snapshot_from_v2(self):
        app = Application()

        topic_v2 = get_topic(self.UpcastFixtureV2)

        aggregate = self.UpcastFixtureV2.create(aa="TEXT", b=1)
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertFalse(hasattr(copy, "c"))
        self.assertFalse(hasattr(copy, "d"))

        app.take_snapshot(aggregate.id)

        # "Deploy" v3.
        del _topic_cache[topic_v2]
        type(self).UpcastFixtureV2 = self.UpcastFixtureV3

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [])
        self.assertFalse(hasattr(copy, "d"))

        # "Deploy" v4.
        del _topic_cache[topic_v2]
        type(self).UpcastFixtureV2 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [])
        self.assertEqual(copy.d, None)

    def test_upcast_created_event_from_v3(self):
        app = Application()

        topic_v3 = get_topic(self.UpcastFixtureV3)
        topic_v3_created = get_topic(self.UpcastFixtureV3.Created)

        aggregate = self.UpcastFixtureV3.create(aa="TEXT", b=1, c=[1, 2])
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertFalse(hasattr(copy, "d"))

        # "Deploy" v3.
        del _topic_cache[topic_v3]
        del _topic_cache[topic_v3_created]
        type(self).UpcastFixtureV3 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, None)

        copy.set_d(value=Decimal("10.0"))
        app.save(copy)

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, 10)

    def test_upcast_aggregate_snapshot_from_v3(self):
        app = Application()

        topic_v3 = get_topic(self.UpcastFixtureV3)

        aggregate = self.UpcastFixtureV3.create(aa="TEXT", b=1, c=[1, 2])
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertFalse(hasattr(copy, "d"))

        app.take_snapshot(aggregate.id)

        # "Deploy" v3.
        del _topic_cache[topic_v3]
        type(self).UpcastFixtureV3 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, None)

        copy.set_d(value=Decimal("10.0"))
        app.save(copy)

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, 10)

        app.take_snapshot(aggregate.id)

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, 10)

    def test_upcast_created_event_from_v4(self):
        app = Application()

        aggregate = self.UpcastFixtureV4.create(aa="TEXT", b=1, c=[1, 2])
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, None)

    def test_upcast_aggregate_snapshot_from_v4(self):
        app = Application()

        aggregate = self.UpcastFixtureV4.create(aa="TEXT", b=1, c=[1, 2])
        app.save(aggregate)

        app.take_snapshot(aggregate.id)

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, None)

    class UpcastFixtureV1(Aggregate):
        def __init__(self, a):
            self.a = a

        @classmethod
        def create(cls, *, a):
            return cls._create(cls.Created, id=uuid4(), a=a)

        class Created(Aggregate.Created):
            a: str

    original_cls_v1 = UpcastFixtureV1

    class UpcastFixtureV2(Aggregate):
        def __init__(self, aa, b):
            self.aa = aa
            self.b = b

        @classmethod
        def create(cls, *, aa, b):
            return cls._create(cls.Created, id=uuid4(), aa=aa, b=b)

        class Created(Aggregate.Created):
            aa: str
            b: str

            class_version = 2

            @staticmethod
            def upcast_v1_v2(state):
                state["aa"] = state.pop("a").upper()
                state["b"] = 0

        class_version = 2

        @staticmethod
        def upcast_v1_v2(state):
            state["aa"] = state.pop("a").upper()
            state["b"] = 0

    original_cls_v2 = UpcastFixtureV2

    class UpcastFixtureV3(Aggregate):
        def __init__(self, aa, b, c):
            self.aa = aa
            self.b = b
            self.c = c

        @classmethod
        def create(cls, *, aa, b, c):
            return cls._create(cls.Created, id=uuid4(), aa=aa, b=b, c=c)

        class Created(Aggregate.Created):
            aa: str
            b: int
            c: list

            class_version = 3

            @staticmethod
            def upcast_v1_v2(state):
                state["aa"] = state.pop("a").upper()
                state["b"] = 0

            @staticmethod
            def upcast_v2_v3(state):
                state["c"] = []

        class_version = 3

        @staticmethod
        def upcast_v1_v2(state):
            state["aa"] = state.pop("a").upper()
            state["b"] = 0

        @staticmethod
        def upcast_v2_v3(state):
            state["c"] = []

    original_cls_v3 = UpcastFixtureV3

    class UpcastFixtureV4(Aggregate):
        def __init__(self, aa, b, c):
            self.aa = aa
            self.b = b
            self.c = c
            self.d: Decimal | None = None

        @classmethod
        def create(cls, *, aa, b, c):
            return cls._create(cls.Created, id=uuid4(), aa=aa, b=b, c=c)

        class Created(Aggregate.Created):
            aa: str
            b: int
            c: list

            class_version = 3

            @staticmethod
            def upcast_v1_v2(state):
                state["aa"] = state.pop("a").upper()
                state["b"] = 0

            @staticmethod
            def upcast_v2_v3(state):
                state["c"] = []

        def set_d(self, value: Decimal):
            self.trigger_event(self.DUpdated, d=value)

        class DUpdated(AggregateEvent):
            d: Decimal

            def apply(self, aggregate: Aggregate) -> None:
                aggregate.d = self.d

        class_version = 4

        @staticmethod
        def upcast_v1_v2(state):
            state["aa"] = state.pop("a").upper()
            state["b"] = 0

        @staticmethod
        def upcast_v2_v3(state):
            state["c"] = []

        @staticmethod
        def upcast_v3_v4(state):
            state["d"] = None
