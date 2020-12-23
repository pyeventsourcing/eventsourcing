from copy import copy
from typing import Dict
from unittest import TestCase

from eventsourcing.application.snapshotting import SnapshottingApplication
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.domain.model.aggregate import BaseAggregateRoot
from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.whitehead import TEntity


class TestUpcastable(TestCase):
    """
    This test case checks that event state can be updated.
    """

    def test_upcast_recorded_state(self):
        # Upcast from original version to original version.
        UpcastableEventFixture.__class_version__ = 0
        state_v0 = {"a": 1}
        obj_state = UpcastableEventFixture.__upcast_state__(state_v0)
        self.assertEqual(obj_state["a"], 1)

        # Upcast from original version to version 1.
        UpcastableEventFixture.__class_version__ = 1
        obj_state = UpcastableEventFixture.__upcast_state__(state_v0)
        self.assertEqual(obj_state["a"], 10000)

        # Upcast from original version to version 2.
        UpcastableEventFixture.__class_version__ = 2
        obj_state = UpcastableEventFixture.__upcast_state__(state_v0)
        self.assertEqual(obj_state["a"], 1000)

        # Upcast from version 1 to version 2.
        state_v1 = {"a": 10000, "__class_version__": 1}
        obj_state = UpcastableEventFixture.__upcast_state__(state_v1)
        self.assertEqual(obj_state["a"], 1000)

        # Upcast from version 2 to version 2.
        state_v2 = {"a": 1000, "__class_version__": 2}
        obj_state = UpcastableEventFixture.__upcast_state__(state_v2)
        self.assertEqual(obj_state["a"], 1000)

    def test_event_state_has_class_version(self):
        # Construct original version.
        UpcastableEventFixture.__class_version__ = 0
        state_v0 = UpcastableEventFixture(a=1).__dict__
        # Check state doesn't have '__class_version__' attribute.
        self.assertEqual(state_v0, {"a": 1})

        # Construct version 1.
        UpcastableEventFixture.__class_version__ = 1
        state_v1 = UpcastableEventFixture(a=1).__dict__
        # Check state does have '__class_version__' attribute.
        self.assertEqual(state_v1, {"a": 1, "__class_version__": 1})

        # Construct version 2.
        UpcastableEventFixture.__class_version__ = 2
        state_v2 = UpcastableEventFixture(a=1).__dict__
        # Check state does have '__class_version__' attribute.
        self.assertEqual(state_v2, {"a": 1, "__class_version__": 2})

    def test_upcast_event_state(self):
        # Construct state with original version of the event class.
        UpcastableEventFixture.__class_version__ = 0
        state_v0 = UpcastableEventFixture(a=1).__dict__
        self.assertEqual(state_v0["a"], 1)

        # Construct state with version 1 of the event class.
        UpcastableEventFixture.__class_version__ = 1
        state_v1 = UpcastableEventFixture(a=10000).__dict__
        self.assertEqual(state_v1["a"], 10000)

        # Check original version is correctly upcast to version 1.
        state_v1_from_v0 = UpcastableEventFixture.__upcast_state__(copy(state_v0))
        self.assertEqual(state_v1, state_v1_from_v0)
        self.assertEqual(state_v0["a"], 1)

        # Check version 1 is correctly upcast to version 1.
        state_v1_from_v1 = UpcastableEventFixture.__upcast_state__(copy(state_v1))
        self.assertEqual(state_v1, state_v1_from_v1)
        self.assertEqual(state_v1["a"], 10000)

        # Construct state with version 2 of the event class.
        UpcastableEventFixture.__class_version__ = 2
        state_v2 = UpcastableEventFixture(a=1000).__dict__

        # Check original version is correctly upcast to version 2.
        state_v2_from_v0 = UpcastableEventFixture.__upcast_state__(copy(state_v0))
        self.assertEqual(state_v2, state_v2_from_v0)

        # Check version 1 is correctly upcast to version 2.
        state_v2_from_v1 = UpcastableEventFixture.__upcast_state__(copy(state_v1))
        self.assertEqual(state_v2, state_v2_from_v1)
        self.assertEqual(state_v1["a"], 10000)
        self.assertEqual(state_v0["a"], 1)

        # Check version 2 is correctly upcast to version 2.
        state_v2_from_v2 = UpcastableEventFixture.__upcast_state__(copy(state_v2))
        self.assertEqual(state_v2, state_v2_from_v2)
        self.assertEqual(state_v2["a"], 1000)
        self.assertEqual(state_v1["a"], 10000)
        self.assertEqual(state_v0["a"], 1)


class UpcastableEventFixture(DomainEvent):
    @classmethod
    def __upcast__(cls, obj_state: Dict, class_version: int):
        if class_version == 0:
            obj_state["a"] *= 10000
        elif class_version == 1:
            obj_state["a"] /= 10
        return obj_state


class TestUpcastingActiveWhenStoringAndRetrievingEvents(TestCase):
    def tearDown(self) -> None:
        # Reset class versions (in case running in suite).
        MultiVersionAggregateFixture.Triggered.__class_version__ = 0
        MultiVersionAggregateFixture.__class_version__ = 0
        del MultiVersionAggregateFixture.Triggered.__upcast__
        del MultiVersionAggregateFixture.Triggered.mutate

    def test_aggregate_state_after_versioning_events(self):
        """
        Mimick evolution of an event class, from original to version 2.

        Could/should just test reconstruct_object() calls __upcast_state__,
        but this test is decoupled from implementation, and simply checks
        upcasting is active when storing and retrieving aggregate state.
        """
        app = SQLAlchemyApplication(persist_event_type=BaseAggregateRoot.Event)
        with app:
            my_aggregate = MultiVersionAggregateFixture.__create__()
            # Trigger without any kwargs (original behaviour).
            my_aggregate.trigger()
            my_aggregate.__save__()

            # Check the default values are used for value and units.
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MultiVersionAggregateFixture)
            self.assertEqual(copy.value, None)  # still uninitialised
            self.assertEqual(copy.units, None)  # still uninitialised

            # Increase the version of the event class (introduce 'value' attribute).
            MultiVersionAggregateFixture.Triggered.__class_version__ = 1
            MultiVersionAggregateFixture.Triggered.__upcast__ = (
                MultiVersionAggregateFixture.Triggered.upcast_v1
            )
            MultiVersionAggregateFixture.Triggered.mutate = (
                MultiVersionAggregateFixture.Triggered.mutate_v1
            )

            # Check v1 code can read original event version (backwards compatibility).
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MultiVersionAggregateFixture)
            self.assertEqual(copy.value, 0)  # gets default
            self.assertEqual(copy.units, None)  # still uninitialised

            # Trigger with value kwarg (first version behaviour).
            my_aggregate.trigger(value=10)
            my_aggregate.__save__()

            # Check v1 code can read original and first event versions.
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MultiVersionAggregateFixture)
            self.assertEqual(copy.value, 10)  # gets set value
            self.assertEqual(copy.units, None)  # still uninitialised

            # Increase the version of the event class.
            MultiVersionAggregateFixture.Triggered.__class_version__ = 2
            MultiVersionAggregateFixture.Triggered.__upcast__ = (
                MultiVersionAggregateFixture.Triggered.upcast_v2
            )
            MultiVersionAggregateFixture.Triggered.mutate = (
                MultiVersionAggregateFixture.Triggered.mutate_v2
            )

            # Check v2 code can read original and first event versions.
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MultiVersionAggregateFixture)
            self.assertEqual(copy.value, 10)
            self.assertEqual(copy.units, "")

            # Trigger with value and units kwargs (second version behaviour).
            my_aggregate.trigger(value=20, units="mm")
            my_aggregate.__save__()

            # Check v2 code can read original, first and second event versions.
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MultiVersionAggregateFixture)
            self.assertEqual(copy.value, 20)
            self.assertEqual(copy.units, "mm")

            # Check original code reads later event versions (forwards compatibility).
            MultiVersionAggregateFixture.Triggered.__class_version__ = 0
            del MultiVersionAggregateFixture.Triggered.__upcast__
            del MultiVersionAggregateFixture.Triggered.mutate
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MultiVersionAggregateFixture)
            self.assertEqual(copy.value, None)  # still uninitialised
            self.assertEqual(copy.units, None)  # still uninitialised

            # Check v1 code reads later versions.
            MultiVersionAggregateFixture.Triggered.__class_version__ = 1
            MultiVersionAggregateFixture.Triggered.__upcast__ = (
                MultiVersionAggregateFixture.Triggered.upcast_v1
            )
            MultiVersionAggregateFixture.Triggered.mutate = (
                MultiVersionAggregateFixture.Triggered.mutate_v1
            )
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MultiVersionAggregateFixture)
            self.assertEqual(copy.value, 20)  # observes event attribute
            self.assertEqual(copy.units, None)  # still uninitialised

    def test_snapshot_state_after_versioning_events(self):
        """
        Mimick evolution of an event class, from original to version 2.

        Could/should just test reconstruct_object() calls __upcast_state__,
        but this test is decoupled from implementation, and simply checks
        upcasting is active when storing and retrieving aggregate state.
        """
        app = SnapshottingApplication.mixin(SQLAlchemyApplication)(
            persist_event_type=BaseAggregateRoot.Event,
        )
        with app:
            my_aggregate = MultiVersionAggregateFixture.__create__()
            # Trigger without any kwargs (original behaviour).
            my_aggregate.trigger()
            my_aggregate.__save__()

            # Take a snapshot.
            app.repository.take_snapshot(my_aggregate.id)

            # Check the default values are used for value and units.
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MultiVersionAggregateFixture)
            self.assertEqual(copy.value, None)
            self.assertEqual(copy.units, None)

            # Increase the version of the aggregate and event class.
            MultiVersionAggregateFixture.__class_version__ = 1
            MultiVersionAggregateFixture.Triggered.__class_version__ = 1
            MultiVersionAggregateFixture.Triggered.__upcast__ = (
                MultiVersionAggregateFixture.Triggered.upcast_v1
            )
            MultiVersionAggregateFixture.Triggered.mutate = (
                MultiVersionAggregateFixture.Triggered.mutate_v1
            )

            # Check v1 code upcasts snapshot (which doesnt have 'value').
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MultiVersionAggregateFixture)
            self.assertEqual(copy.value, 0)  # gets default
            self.assertEqual(copy.units, None)

            # Trigger with value kwarg (first version behaviour).
            my_aggregate.trigger(value=10)
            my_aggregate.__save__()

            # Check v1 code can read original and first event versions.
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MultiVersionAggregateFixture)
            self.assertEqual(copy.value, 10)
            self.assertEqual(copy.units, None)

            # Take a snapshot.
            app.repository.take_snapshot(my_aggregate.id)

            # Check the default values are used for value and units.
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MultiVersionAggregateFixture)
            self.assertEqual(copy.value, 10)
            self.assertEqual(copy.units, None)

            # Increase the version of the aggregate and event class.
            MultiVersionAggregateFixture.__class_version__ = 2
            MultiVersionAggregateFixture.Triggered.__class_version__ = 2
            MultiVersionAggregateFixture.Triggered.__upcast__ = (
                MultiVersionAggregateFixture.Triggered.upcast_v2
            )
            MultiVersionAggregateFixture.Triggered.mutate = (
                MultiVersionAggregateFixture.Triggered.mutate_v2
            )

            # Check v2 code upcasts snapshot (which doesnt have 'units').
            copy = app.repository[my_aggregate.id]
            assert isinstance(copy, MultiVersionAggregateFixture)
            self.assertEqual(copy.value, 10)
            self.assertEqual(copy.units, "")  # gets default


class MultiVersionAggregateFixture(BaseAggregateRoot):
    DEFAULT_VALUE = 0
    DEFAULT_UNITS = ""

    @classmethod
    def __upcast__(cls, obj_state: Dict, class_version: int) -> Dict:
        if class_version == 0:
            obj_state["value"] = cls.DEFAULT_VALUE
        elif class_version == 1:
            obj_state["units"] = cls.DEFAULT_UNITS
        return obj_state

    def __init__(self, **kwargs):
        super(MultiVersionAggregateFixture, self).__init__(**kwargs)
        self.value = None
        self.units = None

    def trigger(self, **kwargs):
        self.__trigger_event__(self.Triggered, **kwargs)

    class Triggered(BaseAggregateRoot.Event):
        @property
        def value(self):
            return self.__dict__["value"]

        @property
        def units(self):
            return self.__dict__["units"]

        def mutate_v1(self, obj: TEntity) -> None:
            obj.value = self.value

        def mutate_v2(self, obj: TEntity) -> None:
            obj.value = self.value
            obj.units = self.units

        @classmethod
        def upcast_v1(cls, obj_state, class_version) -> None:
            if class_version == 0:
                obj_state["value"] = MultiVersionAggregateFixture.DEFAULT_VALUE
            return obj_state

        @classmethod
        def upcast_v2(cls, obj_state, class_version) -> None:
            if class_version == 0:
                obj_state["value"] = MultiVersionAggregateFixture.DEFAULT_VALUE
            elif class_version == 1:
                obj_state["units"] = MultiVersionAggregateFixture.DEFAULT_UNITS
            return obj_state
