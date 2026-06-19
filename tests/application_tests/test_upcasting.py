from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, ClassVar
from unittest import TestCase
from uuid import uuid4

from eventsourcing.application import Application
from eventsourcing.domain import Aggregate, AggregateEvent
from eventsourcing.utils import EnvType, _topic_cache, get_topic


class TestUpcasting(TestCase):
    env: ClassVar[EnvType | None] = None

    def setUp(self) -> None:
        os.environ["IS_SNAPSHOTTING_ENABLED"] = "y"

    def tearDown(self) -> None:
        del os.environ["IS_SNAPSHOTTING_ENABLED"]
        TestUpcasting.UpcastFixtureV1 = TestUpcasting.original_cls_v1  # type: ignore[misc]
        TestUpcasting.UpcastFixtureV2 = TestUpcasting.original_cls_v2  # type: ignore[misc]
        TestUpcasting.UpcastFixtureV3 = TestUpcasting.original_cls_v3  # type: ignore[misc]

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

    def construct_application(self) -> Application:
        return Application(env=self.env)

    def test_upcast_created_event_from_v1(self) -> None:
        app = self.construct_application()

        topic_v1 = get_topic(self.UpcastFixtureV1)
        topic_v1_created = get_topic(self.UpcastFixtureV1.Created)

        aggregate = self.UpcastFixtureV1.create(a="text")
        app.save(aggregate)
        copy1: TestUpcasting.UpcastFixtureV1 = app.repository.get(aggregate.id)
        self.assertEqual(copy1.a, "text")
        self.assertFalse(hasattr(copy1, "b"))
        self.assertFalse(hasattr(copy1, "c"))
        self.assertFalse(hasattr(copy1, "d"))

        # "Deploy" v2.
        del _topic_cache[topic_v1]
        del _topic_cache[topic_v1_created]
        TestUpcasting.UpcastFixtureV1 = self.UpcastFixtureV2  # type: ignore[assignment, misc]

        copy2: TestUpcasting.UpcastFixtureV2 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy2, "a"))
        self.assertEqual(copy2.aa, "TEXT")
        self.assertEqual(copy2.b, 0)
        self.assertFalse(hasattr(copy2, "c"))
        self.assertFalse(hasattr(copy2, "d"))

        # "Deploy" v3.
        del _topic_cache[topic_v1]
        del _topic_cache[topic_v1_created]
        TestUpcasting.UpcastFixtureV1 = self.UpcastFixtureV3  # type: ignore[assignment, misc]

        copy3: TestUpcasting.UpcastFixtureV3 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy3, "a"))
        self.assertEqual(copy3.aa, "TEXT")
        self.assertEqual(copy3.b, 0)
        self.assertEqual(copy3.c, [])

        # "Deploy" v4.
        del _topic_cache[topic_v1]
        TestUpcasting.UpcastFixtureV1 = self.UpcastFixtureV4  # type: ignore[assignment, misc]

        copy4: TestUpcasting.UpcastFixtureV4 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy4, "a"))
        self.assertEqual(copy4.aa, "TEXT")
        self.assertEqual(copy4.b, 0)
        self.assertEqual(copy4.c, [])
        self.assertEqual(copy4.d, None)

    def test_upcast_aggregate_snapshot_from_v1(self) -> None:
        app = self.construct_application()

        topic_v1 = get_topic(self.UpcastFixtureV1)

        aggregate = self.UpcastFixtureV1.create(a="text")
        app.save(aggregate)
        copy1: TestUpcasting.UpcastFixtureV1 = app.repository.get(aggregate.id)
        self.assertEqual(copy1.a, "text")
        self.assertFalse(hasattr(copy1, "b"))
        self.assertFalse(hasattr(copy1, "c"))
        self.assertFalse(hasattr(copy1, "d"))

        app.take_snapshot(aggregate.id)

        # "Deploy" v2.
        del _topic_cache[topic_v1]
        TestUpcasting.UpcastFixtureV1 = self.UpcastFixtureV2  # type: ignore[assignment, misc]

        copy2: TestUpcasting.UpcastFixtureV2 = app.repository.get(aggregate.id)
        self.assertEqual(copy2.aa, "TEXT")
        self.assertEqual(copy2.b, 0)
        self.assertFalse(hasattr(copy2, "c"))
        self.assertFalse(hasattr(copy2, "d"))

        # "Deploy" v3.
        del _topic_cache[topic_v1]
        TestUpcasting.UpcastFixtureV1 = self.UpcastFixtureV3  # type: ignore[assignment, misc]

        copy3: TestUpcasting.UpcastFixtureV3 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy3, "a"))
        self.assertEqual(copy3.aa, "TEXT")
        self.assertEqual(copy3.b, 0)
        self.assertEqual(copy3.c, [])
        self.assertFalse(hasattr(copy3, "d"))

        # "Deploy" v4.
        del _topic_cache[topic_v1]
        TestUpcasting.UpcastFixtureV1 = self.UpcastFixtureV4  # type: ignore[assignment, misc]

        copy4: TestUpcasting.UpcastFixtureV4 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy4, "a"))
        self.assertEqual(copy4.aa, "TEXT")
        self.assertEqual(copy4.b, 0)
        self.assertEqual(copy4.c, [])
        self.assertEqual(copy4.d, None)

    def test_upcast_created_event_from_v2(self) -> None:
        app = self.construct_application()

        topic_v2 = get_topic(self.UpcastFixtureV2)
        topic_v2_created = get_topic(self.UpcastFixtureV2.Created)

        aggregate = self.UpcastFixtureV2.create(aa="TEXT", b=1)
        app.save(aggregate)
        copy1: TestUpcasting.UpcastFixtureV2 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy1, "a"))
        self.assertEqual(copy1.aa, "TEXT")
        self.assertEqual(copy1.b, 1)
        self.assertFalse(hasattr(copy1, "c"))
        self.assertFalse(hasattr(copy1, "d"))

        # "Deploy" v3.
        del _topic_cache[topic_v2]
        del _topic_cache[topic_v2_created]
        TestUpcasting.UpcastFixtureV2 = self.UpcastFixtureV3  # type: ignore[assignment, misc]

        copy2: TestUpcasting.UpcastFixtureV3 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy2, "a"))
        self.assertEqual(copy2.aa, "TEXT")
        self.assertEqual(copy2.b, 1)
        self.assertEqual(copy2.c, [])
        self.assertFalse(hasattr(copy2, "d"))

        # "Deploy" v4.
        del _topic_cache[topic_v2]
        del _topic_cache[topic_v2_created]
        TestUpcasting.UpcastFixtureV2 = self.UpcastFixtureV4  # type: ignore[assignment, misc]

        copy3: TestUpcasting.UpcastFixtureV4 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy3, "a"))
        self.assertEqual(copy3.aa, "TEXT")
        self.assertEqual(copy3.b, 1)
        self.assertEqual(copy3.c, [])
        self.assertEqual(copy3.d, None)

    def test_upcast_aggregate_snapshot_from_v2(self) -> None:
        app = self.construct_application()

        topic_v2 = get_topic(self.UpcastFixtureV2)

        aggregate = self.UpcastFixtureV2.create(aa="TEXT", b=1)
        app.save(aggregate)
        copy1: TestUpcasting.UpcastFixtureV2 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy1, "a"))
        self.assertEqual(copy1.aa, "TEXT")
        self.assertEqual(copy1.b, 1)
        self.assertFalse(hasattr(copy1, "c"))
        self.assertFalse(hasattr(copy1, "d"))

        app.take_snapshot(aggregate.id)

        # "Deploy" v3.
        del _topic_cache[topic_v2]
        TestUpcasting.UpcastFixtureV2 = self.UpcastFixtureV3  # type: ignore[assignment, misc]

        copy2: TestUpcasting.UpcastFixtureV3 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy2, "a"))
        self.assertEqual(copy2.aa, "TEXT")
        self.assertEqual(copy2.b, 1)
        self.assertEqual(copy2.c, [])
        self.assertFalse(hasattr(copy2, "d"))

        # "Deploy" v4.
        del _topic_cache[topic_v2]
        TestUpcasting.UpcastFixtureV2 = self.UpcastFixtureV4  # type: ignore[assignment, misc]

        copy3: TestUpcasting.UpcastFixtureV4 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy3, "a"))
        self.assertEqual(copy3.aa, "TEXT")
        self.assertEqual(copy3.b, 1)
        self.assertEqual(copy3.c, [])
        self.assertEqual(copy3.d, None)

    def test_upcast_created_event_from_v3(self) -> None:
        app = self.construct_application()

        topic_v3 = get_topic(self.UpcastFixtureV3)
        topic_v3_created = get_topic(self.UpcastFixtureV3.Created)

        aggregate = self.UpcastFixtureV3.create(aa="TEXT", b=1, c=[1, 2])
        app.save(aggregate)
        copy1: TestUpcasting.UpcastFixtureV3 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy1, "a"))
        self.assertEqual(copy1.aa, "TEXT")
        self.assertEqual(copy1.b, 1)
        self.assertEqual(copy1.c, [1, 2])
        self.assertFalse(hasattr(copy1, "d"))

        # "Deploy" v4.
        del _topic_cache[topic_v3]
        del _topic_cache[topic_v3_created]
        TestUpcasting.UpcastFixtureV3 = self.UpcastFixtureV4  # type: ignore[assignment, misc]

        copy2: TestUpcasting.UpcastFixtureV4 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy2, "a"))
        self.assertEqual(copy2.aa, "TEXT")
        self.assertEqual(copy2.b, 1)
        self.assertEqual(copy2.c, [1, 2])
        self.assertEqual(copy2.d, None)

        copy2.set_d(value=Decimal("10.0"))
        app.save(copy2)

        copy3: TestUpcasting.UpcastFixtureV4 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy3, "a"))
        self.assertEqual(copy3.aa, "TEXT")
        self.assertEqual(copy3.b, 1)
        self.assertEqual(copy3.c, [1, 2])
        self.assertEqual(copy3.d, 10)

    def test_upcast_aggregate_snapshot_from_v3(self) -> None:
        app = self.construct_application()

        topic_v3 = get_topic(self.UpcastFixtureV3)

        aggregate = self.UpcastFixtureV3.create(aa="TEXT", b=1, c=[1, 2])
        app.save(aggregate)
        copy1: TestUpcasting.UpcastFixtureV3 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy1, "a"))
        self.assertEqual(copy1.aa, "TEXT")
        self.assertEqual(copy1.b, 1)
        self.assertEqual(copy1.c, [1, 2])
        self.assertFalse(hasattr(copy1, "d"))

        app.take_snapshot(aggregate.id)

        # "Deploy" v4.
        del _topic_cache[topic_v3]
        TestUpcasting.UpcastFixtureV3 = self.UpcastFixtureV4  # type: ignore[assignment, misc]

        copy2: TestUpcasting.UpcastFixtureV4 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy2, "a"))
        self.assertEqual(copy2.aa, "TEXT")
        self.assertEqual(copy2.b, 1)
        self.assertEqual(copy2.c, [1, 2])
        self.assertEqual(copy2.d, None)

        copy2.set_d(value=Decimal("10.0"))
        app.save(copy2)

        copy3: TestUpcasting.UpcastFixtureV4 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy3, "a"))
        self.assertEqual(copy3.aa, "TEXT")
        self.assertEqual(copy3.b, 1)
        self.assertEqual(copy3.c, [1, 2])
        self.assertEqual(copy3.d, 10)

        app.take_snapshot(aggregate.id)

        copy4: TestUpcasting.UpcastFixtureV4 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy3, "a"))
        self.assertEqual(copy4.aa, "TEXT")
        self.assertEqual(copy4.b, 1)
        self.assertEqual(copy4.c, [1, 2])
        self.assertEqual(copy4.d, 10)

    def test_upcast_created_event_from_v4(self) -> None:
        app = self.construct_application()

        aggregate = self.UpcastFixtureV4.create(aa="TEXT", b=1, c=[1, 2])
        app.save(aggregate)
        copy: TestUpcasting.UpcastFixtureV4 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, None)

    def test_upcast_aggregate_snapshot_from_v4(self) -> None:
        app = self.construct_application()

        aggregate = self.UpcastFixtureV4.create(aa="TEXT", b=1, c=[1, 2])
        app.save(aggregate)

        app.take_snapshot(aggregate.id)

        copy: TestUpcasting.UpcastFixtureV4 = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, "a"))
        self.assertEqual(copy.aa, "TEXT")
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, None)

    class UpcastFixtureV1(Aggregate):
        def __init__(self, a: str) -> None:
            self.a = a

        @classmethod
        def create(cls, *, a: str) -> TestUpcasting.UpcastFixtureV1:
            return cls._create(cls.Created, id=uuid4(), a=a)

        class Created(Aggregate.Created):
            a: str

    original_cls_v1 = UpcastFixtureV1

    class UpcastFixtureV2(Aggregate):
        def __init__(self, aa: str, b: int) -> None:
            self.aa = aa
            self.b = b

        @classmethod
        def create(cls, *, aa: str, b: int) -> TestUpcasting.UpcastFixtureV2:
            return cls._create(cls.Created, id=uuid4(), aa=aa, b=b)

        class Created(Aggregate.Created):
            aa: str
            b: str

            class_version = 2

            @staticmethod
            def upcast_v1_v2(state: dict[str, Any]) -> None:
                state["aa"] = state.pop("a").upper()
                state["b"] = 0

        class_version = 2

        @staticmethod
        def upcast_v1_v2(state: dict[str, Any]) -> None:
            state["aa"] = state.pop("a").upper()
            state["b"] = 0

    original_cls_v2 = UpcastFixtureV2

    class UpcastFixtureV3(Aggregate):
        def __init__(self, aa: str, b: int, c: list[int]) -> None:
            self.aa = aa
            self.b = b
            self.c = c

        @classmethod
        def create(
            cls, *, aa: str, b: int, c: list[int]
        ) -> TestUpcasting.UpcastFixtureV3:
            return cls._create(cls.Created, id=uuid4(), aa=aa, b=b, c=c)

        class Created(Aggregate.Created):
            aa: str
            b: int
            c: list[int]

            class_version = 3

            @staticmethod
            def upcast_v1_v2(state: dict[str, Any]) -> None:
                state["aa"] = state.pop("a").upper()
                state["b"] = 0

            @staticmethod
            def upcast_v2_v3(state: dict[str, Any]) -> None:
                state["c"] = []

        class_version = 3

        @staticmethod
        def upcast_v1_v2(state: dict[str, Any]) -> None:
            state["aa"] = state.pop("a").upper()
            state["b"] = 0

        @staticmethod
        def upcast_v2_v3(state: dict[str, Any]) -> None:
            state["c"] = []

    original_cls_v3 = UpcastFixtureV3

    class UpcastFixtureV4(Aggregate):
        def __init__(self, aa: str, b: int, c: list[int]) -> None:
            self.aa = aa
            self.b = b
            self.c = c
            self.d: Decimal | None = None

        @classmethod
        def create(
            cls, *, aa: str, b: int, c: list[int]
        ) -> TestUpcasting.UpcastFixtureV4:
            return cls._create(cls.Created, id=uuid4(), aa=aa, b=b, c=c)

        class Created(Aggregate.Created):
            aa: str
            b: int
            c: list[int]

            class_version = 3

            @staticmethod
            def upcast_v1_v2(state: dict[str, Any]) -> None:
                state["aa"] = state.pop("a").upper()
                state["b"] = 0

            @staticmethod
            def upcast_v2_v3(state: dict[str, Any]) -> None:
                state["c"] = []

        def set_d(self, value: Decimal) -> None:
            self.trigger_event(self.DUpdated, d=value)

        class DUpdated(AggregateEvent):
            d: Decimal

            def apply(self, aggregate: TestUpcasting.UpcastFixtureV4) -> None:
                aggregate.d = self.d

        class_version = 4

        @staticmethod
        def upcast_v1_v2(state: dict[str, Any]) -> None:
            state["aa"] = state.pop("a").upper()
            state["b"] = 0

        @staticmethod
        def upcast_v2_v3(state: dict[str, Any]) -> None:
            state["c"] = []

        @staticmethod
        def upcast_v3_v4(state: dict[str, Any]) -> None:
            state["d"] = None
