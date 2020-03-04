from unittest import TestCase

from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.domain.model.aggregate import BaseAggregateRoot
from eventsourcing.whitehead import TEntity


class MyAggregate(BaseAggregateRoot):

    DEFAULT_VALUE = 0
    DEFAULT_UNITS = ''

    def __init__(self, **kwargs):
        super(MyAggregate, self).__init__(**kwargs)
        self.value = self.DEFAULT_VALUE
        self.units = self.DEFAULT_UNITS

    def trigger(self, **kwargs):
        self.__trigger_event__(self.Triggered, **kwargs)

    class Triggered(BaseAggregateRoot.Event):
        @property
        def value(self):
            return self.__dict__['value']

        @property
        def units(self):
            return self.__dict__['units']

        def mutate_v1(self, obj: TEntity) -> None:
            obj.value = self.value

        def mutate_v2(self, obj: TEntity) -> None:
            obj.value = self.value
            obj.units = self.units

        @classmethod
        def upcast_v1(cls, obj_state, class_version) -> None:
            if class_version == 0:
                obj_state['value'] = MyAggregate.DEFAULT_VALUE
            return obj_state

        @classmethod
        def upcast_v2(cls, obj_state, class_version) -> None:
            if class_version == 0:
                obj_state['value'] = MyAggregate.DEFAULT_VALUE
            elif class_version == 1:
                obj_state['units'] = MyAggregate.DEFAULT_UNITS
            return obj_state


class TestVersioningEvents(TestCase):
    def test(self):
        app = SQLAlchemyApplication(persist_event_type=BaseAggregateRoot.Event)
        with app:
            my_aggregate = MyAggregate.__create__()
            # Trigger without any kwargs (original behaviour).
            my_aggregate.trigger()
            my_aggregate.__save__()

            # Check the default values are used for value and units.
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MyAggregate)
            self.assertEqual(copy.value, 0)
            self.assertEqual(copy.units, '')

            # Increase the version of the event class.
            MyAggregate.Triggered.__class_version__ = 1
            MyAggregate.Triggered.upcast = MyAggregate.Triggered.upcast_v1
            MyAggregate.Triggered.mutate = MyAggregate.Triggered.mutate_v1

            # Check v1 code can read original event version (backwards compatibility).
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MyAggregate)
            self.assertEqual(copy.value, 0)
            self.assertEqual(copy.units, '')

            # Trigger with value kwarg (first version behaviour).
            my_aggregate.trigger(value=10)
            my_aggregate.__save__()

            # Check v1 code can read original and first event versions.
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MyAggregate)
            self.assertEqual(copy.value, 10)
            self.assertEqual(copy.units, '')

            # Increase the version of the event class.
            MyAggregate.Triggered.__class_version__ = 2
            MyAggregate.Triggered.upcast = MyAggregate.Triggered.upcast_v2
            MyAggregate.Triggered.mutate = MyAggregate.Triggered.mutate_v2

            # Check v2 code can read original and first event versions.
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MyAggregate)
            self.assertEqual(copy.value, 10)
            self.assertEqual(copy.units, '')

            # Trigger with value and units kwargs (second version behaviour).
            my_aggregate.trigger(value=20, units='mm')
            my_aggregate.__save__()

            # Check v2 code can read original, first and second event versions.
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MyAggregate)
            self.assertEqual(copy.value, 20)
            self.assertEqual(copy.units, 'mm')

            # Check original code reads later event versions (forwards compatibility).
            MyAggregate.Triggered.__class_version__ = 0
            del(MyAggregate.Triggered.upcast)
            del(MyAggregate.Triggered.mutate)
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MyAggregate)
            self.assertEqual(copy.value, 0)   # ignores event attribute
            self.assertEqual(copy.units, '')  # ignores event attribute

            # Check v1 code reads later versions.
            MyAggregate.Triggered.__class_version__ = 1
            MyAggregate.Triggered.upcast = MyAggregate.Triggered.upcast_v1
            MyAggregate.Triggered.mutate = MyAggregate.Triggered.mutate_v1
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MyAggregate)
            self.assertEqual(copy.value, 20)  # observes event attribute
            self.assertEqual(copy.units, '')  # ignores event attribute
