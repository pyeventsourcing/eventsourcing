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

        aggregate = self.UpcastFixtureV1.create(a='text')
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'text')
        self.assertFalse(hasattr(copy, 'b'))
        self.assertFalse(hasattr(copy, 'c'))
        self.assertFalse(hasattr(copy, 'd'))

        # "Deploy" v2.
        type(self).UpcastFixtureV1 = self.UpcastFixtureV2

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 0)
        self.assertFalse(hasattr(copy, 'c'))
        self.assertFalse(hasattr(copy, 'd'))

        # "Deploy" v3.
        type(self).UpcastFixtureV1 = self.UpcastFixtureV3

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])

        # "Deploy" v4.
        type(self).UpcastFixtureV1 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])
        self.assertEqual(copy.d, None)

    def test_upcast_aggregate_snapshot_from_v1(self):
        app = Application()

        aggregate = self.UpcastFixtureV1.create(a='text')
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.a, 'text')
        self.assertFalse(hasattr(copy, 'b'))
        self.assertFalse(hasattr(copy, 'c'))
        self.assertFalse(hasattr(copy, 'd'))

        app.take_snapshot(aggregate.id)

        # "Deploy" v2.
        type(self).UpcastFixtureV1 = self.UpcastFixtureV2

        copy = app.repository.get(aggregate.id)
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 0)
        self.assertFalse(hasattr(copy, 'c'))
        self.assertFalse(hasattr(copy, 'd'))

        # "Deploy" v3.
        type(self).UpcastFixtureV1 = self.UpcastFixtureV3

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])
        self.assertFalse(hasattr(copy, 'd'))

        # "Deploy" v4.
        type(self).UpcastFixtureV1 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 0)
        self.assertEqual(copy.c, [])
        self.assertEqual(copy.d, None)

    def test_upcast_created_event_from_v2(self):
        app = Application()

        aggregate = self.UpcastFixtureV2.create(A='TEXT', b=1)
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 1)
        self.assertFalse(hasattr(copy, 'c'))
        self.assertFalse(hasattr(copy, 'd'))

        # "Deploy" v3.
        type(self).UpcastFixtureV2 = self.UpcastFixtureV3

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [])
        self.assertFalse(hasattr(copy, 'd'))

        # "Deploy" v4.
        type(self).UpcastFixtureV2 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [])
        self.assertEqual(copy.d, None)

    def test_upcast_aggregate_snapshot_from_v2(self):
        app = Application()

        aggregate = self.UpcastFixtureV2.create(A='TEXT', b=1)
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 1)
        self.assertFalse(hasattr(copy, 'c'))
        self.assertFalse(hasattr(copy, 'd'))

        app.take_snapshot(aggregate.id)

        # "Deploy" v3.
        type(self).UpcastFixtureV2 = self.UpcastFixtureV3

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [])
        self.assertFalse(hasattr(copy, 'd'))

        # "Deploy" v4.
        type(self).UpcastFixtureV2 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [])
        self.assertEqual(copy.d, None)

    def test_upcast_created_event_from_v3(self):
        app = Application()

        aggregate = self.UpcastFixtureV3.create(A='TEXT', b=1, c=[1, 2])
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertFalse(hasattr(copy, 'd'))

        # "Deploy" v3.
        type(self).UpcastFixtureV3 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, None)

        copy.set_d(value=Decimal('10.0'))
        app.save(copy)

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, 10)

    def test_upcast_aggregate_snapshot_from_v3(self):
        app = Application()

        aggregate = self.UpcastFixtureV3.create(A='TEXT', b=1, c=[1, 2])
        app.save(aggregate)
        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertFalse(hasattr(copy, 'd'))

        app.take_snapshot(aggregate.id)

        # "Deploy" v3.
        type(self).UpcastFixtureV3 = self.UpcastFixtureV4

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, None)

        copy.set_d(value=Decimal('10.0'))
        app.save(copy)

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, 10)

        app.take_snapshot(aggregate.id)

        copy = app.repository.get(aggregate.id)
        self.assertFalse(hasattr(copy, 'a'))
        self.assertEqual(copy.A, 'TEXT')
        self.assertEqual(copy.b, 1)
        self.assertEqual(copy.c, [1, 2])
        self.assertEqual(copy.d, 10)

    class UpcastFixtureV1(Aggregate):
        _class_version_ = 1

        @classmethod
        def create(cls, *, a):
            return cls._create_(cls.Created, id=uuid4(), a=a)

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
        def create(cls, *, A, b):
            return cls._create_(cls.Created, id=uuid4(), A=A, b=b)

        def __init__(self, A, b, **kwargs):
            super().__init__(**kwargs)
            self.A = A
            self.b = b

        @staticmethod
        def _upcast_v1_v2_(state):
            state['A'] = state.pop('a').upper()
            state['b'] = 0

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            _class_version_ = 2

            A: str
            b: str

            @staticmethod
            def _upcast_v1_v2_(state):
                state['A'] = state.pop('a').upper()
                state['b'] = 0

    original_cls_v2 = UpcastFixtureV2

    class UpcastFixtureV3(Aggregate):
        _class_version_ = 3

        @classmethod
        def create(cls, *, A, b, c):
            return cls._create_(cls.Created, id=uuid4(), A=A, b=b, c=c)

        def __init__(self, A, b, c, **kwargs):
            super().__init__(**kwargs)
            self.A = A
            self.b = b
            self.c = c

        @staticmethod
        def _upcast_v1_v2_(state):
            state['A'] = state.pop('a').upper()
            state['b'] = 0

        @staticmethod
        def _upcast_v2_v3_(state):
            state['c'] = []

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            _class_version_ = 3
            A: str
            b: int
            c: List

            @staticmethod
            def _upcast_v1_v2_(state):
                state['A'] = state.pop('a').upper()
                state['b'] = 0

            @staticmethod
            def _upcast_v2_v3_(state):
                state['c'] = []

    original_cls_v3 = UpcastFixtureV3

    class UpcastFixtureV4(Aggregate):
        _class_version_ = 4

        def __init__(self, A, b, c, **kwargs):
            super().__init__(**kwargs)
            self.A = A
            self.b = b
            self.c = c
            self.d: Optional[Decimal] = None

        @staticmethod
        def _upcast_v1_v2_(state):
            state['A'] = state.pop('a').upper()
            state['b'] = 0

        @staticmethod
        def _upcast_v2_v3_(state):
            state['c'] = []

        @staticmethod
        def _upcast_v3_v4_(state):
            state['d'] = None

        @dataclass(frozen=True)
        class Created(Aggregate.Created):
            _class_version_ = 3
            a: str
            b: int
            c: List

            @staticmethod
            def _upcast_v1_v2_(state):
                state['A'] = state.pop('a').upper()
                state['b'] = 0

            @staticmethod
            def _upcast_v2_v3_(state):
                state['c'] = []

        def set_d(self, value: Decimal):
            self._trigger_(self.DUpdated, d=value)

        @dataclass(frozen=True)
        class DUpdated(Aggregate.Event):
            d: Decimal

            def apply(self, aggregate: "Aggregate") -> None:
                aggregate.d = self.d
