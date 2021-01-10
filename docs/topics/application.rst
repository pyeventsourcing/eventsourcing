============
Applications
============

This section discusses how an :doc:`event-sourced domain model
</topics/domain>` can be combined with :doc:`library's persistence
mechanism </topics/persistence>` to make an event sourced application.

.. contents:: :local:

Firstly let's recall the ``World`` aggregate discussed in
the documentation about the library's :doc:`event-sourced domain module
</topics/domain>`.

.. code:: python

    from uuid import uuid4

    from eventsourcing.domain import Aggregate


    class World(Aggregate):
        def __init__(self, **kwargs):
            super(World, self).__init__(**kwargs)
            self.history = []

        @classmethod
        def create(self):
            return self._create_(
                event_class=Aggregate.Created,
                uuid=uuid4(),
            )

        def make_it_so(self, what):
            self._trigger_(World.SomethingHappened, what=what)

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
            return world.uuid

        def make_it_so(self, world_id, what):
            world = self.repository.get(world_id)
            world.make_it_so(what)
            self.save(world)

        def get_world_history(self, world_id):
            world = self.repository.get(world_id)
            return list(world.history)


.. code:: python

    application = WorldsApplication()

    world_id = application.create_world()

    application.make_it_so(world_id, 'dinosaurs')
    application.make_it_so(world_id, 'trucks')
    application.make_it_so(world_id, 'internet')

    history = application.get_world_history(world_id)
    assert history[0] == 'dinosaurs'
    assert history[1] == 'trucks'
    assert history[2] == 'internet'


.. code:: python

    from eventsourcing.persistence import Notification


    section = application.log['1,10']

    assert isinstance(section.items[0], Notification)
    assert section.items[0].id == 1
    assert section.items[1].id == 2
    assert section.items[2].id == 3
    assert section.items[3].id == 4

    assert section.items[0].originator_id == world_id
    assert section.items[1].originator_id == world_id
    assert section.items[2].originator_id == world_id
    assert section.items[3].originator_id == world_id

    assert section.items[0].originator_version == 1
    assert section.items[1].originator_version == 2
    assert section.items[2].originator_version == 3
    assert section.items[3].originator_version == 4

    assert 'Aggregate.Created' in section.items[0].topic
    assert 'World.SomethingHappened' in section.items[1].topic
    assert 'World.SomethingHappened' in section.items[2].topic
    assert 'World.SomethingHappened' in section.items[3].topic

    assert b'dinosaurs' in section.items[1].state
    assert b'trucks' in section.items[2].state
    assert b'internet' in section.items[3].state


.. code:: python

    import os

    os.environ['IS_SNAPSHOTTING_ENABLED'] = 'y'
    application = WorldsApplication()

    world_id = application.create_world()

    application.make_it_so(world_id, 'dinosaurs')
    application.make_it_so(world_id, 'trucks')
    application.make_it_so(world_id, 'internet')

    application.take_snapshot(world_id, version=2)


.. code:: python


    from tempfile import NamedTemporaryFile

    tmpfile = NamedTemporaryFile(suffix="_eventsourcing_test.db")
    tmpfile.name

    os.environ['INFRASTRUCTURE_FACTORY'] = 'eventsourcing.sqlite:Factory'
    os.environ['SQLITE_DBNAME'] = tmpfile.name
    os.environ['DO_CREATE_TABLE'] = 'yes'
    application = WorldsApplication()

    world_id = application.create_world()

    application.make_it_so(world_id, 'dinosaurs')
    application.make_it_so(world_id, 'trucks')
    application.make_it_so(world_id, 'internet')

    application.take_snapshot(world_id, version=2)


.. code:: python

    os.environ['INFRASTRUCTURE_FACTORY'] = 'eventsourcing.sqlite:Factory'
    os.environ['SQLITE_DBNAME'] = tmpfile.name
    os.environ['DO_CREATE_TABLE'] = 'no'
    application = WorldsApplication()

    history = application.get_world_history(world_id)
    assert history[0] == 'dinosaurs'
    assert history[1] == 'trucks'
    assert history[2] == 'internet'



Classes
=======

.. automodule:: eventsourcing.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
