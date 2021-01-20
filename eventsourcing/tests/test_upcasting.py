import os
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional
from unittest import TestCase
from uuid import uuid4

from eventsourcing.application import Application
from eventsourcing.domain import Aggregate


class TestUpcasting(TestCase):

    def setUp(self) -> None:
        os.environ["IS_SNAPSHOTTING_ENABLED"] = 'y'

    def tearDown(self) -> None:
        del os.environ["IS_SNAPSHOTTING_ENABLED"]
        type(self).UpcastFixtureV1 = type(self).original_cls_v1
        type(self).UpcastFixtureV2 = type(self).original_cls_v2
        type(self).UpcastFixtureV3 = type(self).original_cls_v3

    def test_upcast_created_event_from_v1(self):
        app = Application()

        aggregate = self.UpcastFixtureV1.create()
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'text')
        self.assertFalse(hasattr(copy, 'b'))

        # Substitute v2.
        type(self).UpcastFixtureV1 = self.UpcastFixtureV2

        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'TEXT')
        self.assertEqual(copy.b, 0)

        # Substitute v3.
        type(self).UpcastFixtureV1 = self.UpcastFixtureV3

        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'TEXT')
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])

    def test_upcast_aggregate_snapshot_from_v1(self):
        app = Application()

        aggregate = self.UpcastFixtureV1.create()
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'text')
        self.assertFalse(hasattr(copy, 'b'))

        app.take_snapshot(aggregate.id)

        # Substitute v2.
        type(self).UpcastFixtureV1 = self.UpcastFixtureV2

        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'TEXT')
        self.assertEqual(copy.b, 0)

        # Substitute v3.
        type(self).UpcastFixtureV1 = self.UpcastFixtureV3

        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'TEXT')
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])

    def test_upcast_created_event_from_v2(self):
        app = Application()

        aggregate = self.UpcastFixtureV2.create()
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'TEXT')
        self.assertEqual(copy.b, 0)

        # Substitute v3.
        type(self).UpcastFixtureV2 = self.UpcastFixtureV3

        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'TEXT')
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])

    def test_upcast_aggregate_snapshot_from_v2(self):
        app = Application()

        aggregate = self.UpcastFixtureV2.create()
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'TEXT')
        self.assertEqual(copy.b, 0)

        app.take_snapshot(aggregate.id)

        # Substitute v3.
        type(self).UpcastFixtureV2 = self.UpcastFixtureV3

        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'TEXT')
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])

    def test_upcast_created_event_from_v3(self):
        app = Application()

        aggregate = self.UpcastFixtureV3.create()
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'TEXT')
        self.assertEqual(copy.b, 0)

        # Substitute v3.
        type(self).UpcastFixtureV3 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'TEXT')
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])
        self.assertEqual(copy.d, None)

        copy.set_d(value=Decimal('10.0'))
        app.save(copy)

        self.assertEqual(copy.d, Decimal('10.0'))

    def test_upcast_aggregate_snapshot_from_v3(self):
        app = Application()

        aggregate = self.UpcastFixtureV3.create()
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'TEXT')
        self.assertEqual(copy.b, 0)

        app.take_snapshot(aggregate.id)

        # Substitute v3.
        type(self).UpcastFixtureV3 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'TEXT')
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])
        self.assertEqual(copy.d, None)

        copy.set_d(value=Decimal('10.0'))
        app.save(copy)

        self.assertEqual(copy.d, Decimal('10.0'))

    class UpcastFixtureV1(Aggregate):
        _class_version_ = 1

        @classmethod
        def create(cls):
            return cls._create_(cls.Created, id=uuid4(), a='text')

        def __init__(self, a, **kwargs):
            super().__init__(**kwargs)
            self.a = a

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            _class_version_ = 1
            a: str

    original_cls_v1 = UpcastFixtureV1

    class UpcastFixtureV2(Aggregate):
        _class_version_ = 2

        @classmethod
        def create(cls):
            return cls._create_(cls.Created, id=uuid4(), a='TEXT', b=1)

        def __init__(self, a, b, **kwargs):
            super().__init__(**kwargs)
            self.a = a
            self.b = b

        @staticmethod
        def _upcast_v1_v2_(d):
            d['a'] = d['a'].upper()
            d['b'] = 0

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            _class_version_ = 2

            a: str
            b: str

            @staticmethod
            def _upcast_v1_v2_(d):
                d['a'] = d['a'].upper()
                d['b'] = 0

    original_cls_v2 = UpcastFixtureV2

    class UpcastFixtureV3(Aggregate):
        _class_version_ = 3

        @classmethod
        def create(cls):
            return cls._create_(cls.Created, id=uuid4(), a='TEXT', b=1, c=[])

        def __init__(self, a, b, c, **kwargs):
            super().__init__(**kwargs)
            self.a = a
            self.b = b
            self.c = c

        @staticmethod
        def _upcast_v1_v2_(d):
            d['a'] = d['a'].upper()
            d['b'] = 0

        @staticmethod
        def _upcast_v2_v3_(d):
            d['c'] = []

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            _class_version_ = 3
            a: str
            b: int
            c: List

            @staticmethod
            def _upcast_v1_v2_(d):
                d['a'] = d['a'].upper()
                d['b'] = 0

            @staticmethod
            def _upcast_v2_v3_(d):
                d['c'] = []

    original_cls_v3 = UpcastFixtureV3

    class UpcastFixtureV4(Aggregate):
        _class_version_ = 4

        def __init__(self, a, b, c, **kwargs):
            super().__init__(**kwargs)
            self.a = a
            self.b = b
            self.c = c
            self.d: Optional[Decimal] = None

        @staticmethod
        def _upcast_v1_v2_(d):
            d['a'] = d['a'].upper()
            d['b'] = 0

        @staticmethod
        def _upcast_v2_v3_(d):
            d['c'] = []

        @staticmethod
        def _upcast_v3_v4_(d):
            d['d'] = None

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            _class_version_ = 3
            a: str
            b: int
            c: List

            @staticmethod
            def _upcast_v1_v2_(d):
                d['a'] = d['a'].upper()
                d['b'] = 0

            @staticmethod
            def _upcast_v2_v3_(d):
                d['c'] = []

        def set_d(self, value: Decimal):
            self._trigger_(self.DUpdated, d=value)

        @dataclass(frozen=True)
        class DUpdated(Aggregate.Event):
            d: Decimal

            def apply(self, aggregate: "Aggregate") -> None:
                aggregate.d = self.d
