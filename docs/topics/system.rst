=======================================
:mod:`eventsourcing.system` --- Systems
=======================================

This module shows how :doc:`event-sourced applications
</topics/application>` can be combined to make an event driven
system.

System of applications
======================

The library's system class...

.. code:: python

    from eventsourcing.system import System

.. code:: python

    from dataclasses import dataclass
    from uuid import uuid4

    from eventsourcing.domain import Aggregate


    class World(Aggregate):
        def __init__(self, **kwargs):
            super(World, self).__init__(**kwargs)
            self.history = []

        @classmethod
        def create(cls):
            return cls._create_(
                event_class=cls.Created,
                id=uuid4(),
            )

        def make_it_so(self, what):
            self._trigger_(World.SomethingHappened, what=what)

        @dataclass(frozen=True)
        class SomethingHappened(Aggregate.Event):
            what: str

            def apply(self, world):
                world.history.append(self.what)


Now let's define an application...


.. code:: python

    from eventsourcing.application import Application


    class WorldsApplication(Application):

        def create_world(self):
            world = World.create()
            self.save(world)
            return world.id

        def make_it_so(self, world_id, what):
            world = self.repository.get(world_id)
            world.make_it_so(what)
            self.save(world)

        def get_world_history(self, world_id):
            world = self.repository.get(world_id)
            return list(world.history)


Now let's define an analytics application...

.. code:: python

    from uuid import uuid5, NAMESPACE_URL

    class Counter(Aggregate):
        def __init__(self, **kwargs):
            super(Counter, self).__init__(**kwargs)
            self.count = 0

        @classmethod
        def create(cls, name):
            return cls._create_(
                event_class=Aggregate.Created,
                id=cls.create_id(name),
            )

        @classmethod
        def create_id(cls, name):
            return uuid5(NAMESPACE_URL, f'/counter/{name}')

        def increment(self):
            self._trigger_(self.Incremented)

        class Incremented(Aggregate.Event):
            def apply(self, counter):
                counter.count += 1


.. code:: python

    from functools import singledispatchmethod

    from eventsourcing.application import AggregateNotFound
    from eventsourcing.system import ProcessApplication


    class Counters(ProcessApplication):

        def policy(self, domain_event, process_event):
            pass

        @singledispatchmethod
        def policy(self, domain_event, process_event):
            """Default policy"""

        @policy.register(World.SomethingHappened)
        def _(self, domain_event, process_event):
            what = domain_event.what
            counter_id = Counter.create_id(what)
            try:
                counter = self.repository.get(counter_id)
            except AggregateNotFound:
                counter = Counter.create(what)
            counter.increment()
            process_event.save(counter)

        def get_count(self, what):
            counter_id = Counter.create_id(what)
            try:
                counter = self.repository.get(counter_id)
            except AggregateNotFound:
                return 0
            return counter.count


.. code:: python

    system = System(pipes=[[WorldsApplication, Counters]])


Single-threaded runner
======================

.. code:: python

    from eventsourcing.system import SingleThreadedRunner


    runner= SingleThreadedRunner(system)
    runner.start()
    worlds = runner.get(WorldsApplication)
    counters = runner.get(Counters)

    world_id1 = worlds.create_world()
    world_id2 = worlds.create_world()
    world_id3 = worlds.create_world()

    assert counters.get_count('dinosaurs') == 0
    assert counters.get_count('trucks') == 0
    assert counters.get_count('internet') == 0

    worlds.make_it_so(world_id1, 'dinosaurs')
    worlds.make_it_so(world_id2, 'dinosaurs')
    worlds.make_it_so(world_id3, 'dinosaurs')

    assert counters.get_count('dinosaurs') == 3
    assert counters.get_count('trucks') == 0
    assert counters.get_count('internet') == 0

    worlds.make_it_so(world_id2, 'trucks')
    worlds.make_it_so(world_id3, 'trucks')

    assert counters.get_count('dinosaurs') == 3
    assert counters.get_count('trucks') == 2
    assert counters.get_count('internet') == 0

    worlds.make_it_so(world_id3, 'internet')

    assert counters.get_count('dinosaurs') == 3
    assert counters.get_count('trucks') == 2
    assert counters.get_count('internet') == 1


Multi-threaded runner
=====================

.. code:: python

    from eventsourcing.system import MultiThreadedRunner


    runner= MultiThreadedRunner(system)
    runner.start()
    worlds = runner.get(WorldsApplication)
    counters = runner.get(Counters)

    world_id1 = worlds.create_world()
    world_id2 = worlds.create_world()
    world_id3 = worlds.create_world()

    worlds.make_it_so(world_id1, 'dinosaurs')
    worlds.make_it_so(world_id2, 'dinosaurs')
    worlds.make_it_so(world_id3, 'dinosaurs')

    worlds.make_it_so(world_id2, 'trucks')
    worlds.make_it_so(world_id3, 'trucks')

    worlds.make_it_so(world_id3, 'internet')

    from time import sleep

    sleep(0.0001)

    assert counters.get_count('dinosaurs') == 3
    assert counters.get_count('trucks') == 2
    assert counters.get_count('internet') == 1

...

Classes
=======

.. automodule:: eventsourcing.system
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
