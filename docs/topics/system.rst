=====================================================
:mod:`~eventsourcing.system` --- Event-driven systems
=====================================================

This module shows how :doc:`event-sourced applications
</topics/application>` can be combined to make an event driven
system.

*this page is under development --- please check back soon*

System of applications
======================

The library's system class...

.. code-block:: python

    from eventsourcing.system import System

.. code-block:: python

    from dataclasses import dataclass
    from uuid import uuid4

    from eventsourcing.domain import Aggregate, event

    class Dog(Aggregate):
        @dataclass(frozen=True)
        class Registered(Aggregate.Created):
            name: str

        @dataclass(frozen=True)
        class TrickAdded(Aggregate.Event):
            trick: str

        @event(Registered)
        def __init__(self, name: str):
            self.name = name
            self.tricks: list[str] = []

        @event(TrickAdded)
        def add_trick(self, trick: str) -> None:
            self.tricks.append(trick)


Now let's define an application...


.. code-block:: python

    from typing import Any
    from uuid import UUID

    from eventsourcing.application import Application


    class DogSchool(Application):
        def register_dog(self, name: str) -> UUID:
            dog = Dog(name)
            self.save(dog)
            return dog.id

        def add_trick(self, dog_id: UUID, trick: str) -> None:
            dog = self.repository.get(dog_id, Dog)
            dog.add_trick(trick)
            self.save(dog)

        def get_dog(self, dog_id: UUID) -> dict[str, Any]:
            dog = self.repository.get(dog_id, Dog)
            return {'name': dog.name, 'tricks': tuple(dog.tricks)}


Now let's define an analytics application...

.. code-block:: python

    from uuid import uuid5, NAMESPACE_URL

    class Counter(Aggregate):
        def __init__(self, name: str):
            self.name = name
            self.count = 0

        @classmethod
        def create_id(cls, name: str) -> UUID:
            return uuid5(NAMESPACE_URL, f'/counters/{name}')

        @event('Incremented')
        def increment(self) -> None:
            self.count += 1


.. code-block:: python

    from eventsourcing.application import AggregateNotFoundError, ProcessingEvent
    from eventsourcing.system import ProcessApplication
    from eventsourcing.dispatch import singledispatchmethod

    class Counters(ProcessApplication):
        @singledispatchmethod
        def policy(self, domain_event: Any, processing_event) -> None:
            """Default policy"""

        @policy.register
        def _(self, domain_event: Dog.TrickAdded, processing_event) -> None:
            trick = domain_event.trick
            try:
                counter_id = Counter.create_id(trick)
                counter = self.repository.get(counter_id, Counter)
            except AggregateNotFoundError:
                counter = Counter(trick)
            counter.increment()
            processing_event.collect_events(counter)

        def get_count(self, trick: str) -> int:
            counter_id = Counter.create_id(trick)
            try:
                counter = self.repository.get(counter_id, Counter)
            except AggregateNotFoundError:
                return 0
            return counter.count


.. code-block:: python

    system = System(pipes=[[DogSchool, Counters]])


Single-threaded runner
======================

.. code-block:: python

    from eventsourcing.system import SingleThreadedRunner, Runner

    runner = SingleThreadedRunner(system)
    runner.start()

    school = runner.get(DogSchool)
    counters = runner.get(Counters)

    dog_id1 = school.register_dog('Billy')
    dog_id2 = school.register_dog('Milly')
    dog_id3 = school.register_dog('Scrappy')

    school.add_trick(dog_id1, 'roll over')
    school.add_trick(dog_id2, 'roll over')
    school.add_trick(dog_id3, 'roll over')

    assert counters.get_count('roll over') == 3
    assert counters.get_count('fetch ball') == 0
    assert counters.get_count('play dead') == 0

    school.add_trick(dog_id1, 'fetch ball')
    school.add_trick(dog_id2, 'fetch ball')

    assert counters.get_count('roll over') == 3
    assert counters.get_count('fetch ball') == 2
    assert counters.get_count('play dead') == 0

    school.add_trick(dog_id1, 'play dead')

    assert counters.get_count('roll over') == 3
    assert counters.get_count('fetch ball') == 2
    assert counters.get_count('play dead') == 1

    runner.stop()

Multi-threaded runner
=====================

.. code-block:: python

    from eventsourcing.system import MultiThreadedRunner

    runner = MultiThreadedRunner(system)
    runner.start()

    school = runner.get(DogSchool)
    counters = runner.get(Counters)

    dog_id1 = school.register_dog('Billy')
    dog_id2 = school.register_dog('Milly')
    dog_id3 = school.register_dog('Scrappy')

    school.add_trick(dog_id1, 'roll over')
    school.add_trick(dog_id2, 'roll over')
    school.add_trick(dog_id3, 'roll over')

    school.add_trick(dog_id1, 'fetch ball')
    school.add_trick(dog_id2, 'fetch ball')

    school.add_trick(dog_id1, 'play dead')

    from time import sleep

    sleep(0.01)

    assert counters.get_count('roll over') == 3
    assert counters.get_count('fetch ball') == 2
    assert counters.get_count('play dead') == 1

    runner.stop()


Code reference
==============

.. automodule:: eventsourcing.system
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
