===========
Quick start
===========

This section shows how to make a simple event sourced
application using classes from the library. It shows the
general story, which is elaborated over the following pages.

.. contents:: :local:


Install library
===============

It is recommended always to install into a virtual environment.

You can use pip to install the library with the 'sqlalchemy' option (other package installers are available).

::

    $ pip install eventsourcing[sqlalchemy]


See the :doc:`Install documentation </topics/installing>` for more information about installing the library.


Define model
============

Having installed the library, open a Python file in your favourite editor. The code snippets below
form a working program. You can either type in the code, or copy and paste. Then run the program.

Firstly let's define a domain model, by defining an aggregate class.
The class ``World`` defined below is a subclass of
:class:`~eventsourcing.domain.model.aggregate.AggregateRoot`.
The class ``World`` has a property called ``history``. It also has an event
sourced attribute called ``ruler``. It has a command method called ``make_it_so``
which triggers a domain event of type ``SomethingHappened`` which is defined as
a nested class. The domain event class ``SomethingHappened`` has a ``mutate()``
method, which happens to append triggered events to the history.

.. code:: python

    from eventsourcing.domain.model.aggregate import AggregateRoot
    from eventsourcing.domain.model.decorators import attribute


    class World(AggregateRoot):

        def __init__(self, ruler=None, **kwargs):
            super(World, self).__init__(**kwargs)
            self._history = []
            self._ruler = ruler

        @property
        def history(self):
            return tuple(self._history)

        @attribute
        def ruler(self):
            """A mutable event-sourced attribute."""

        def make_it_so(self, something):
            self.__trigger_event__(World.SomethingHappened, what=something)

        class SomethingHappened(AggregateRoot.Event):
            def mutate(self, obj):
                obj._history.append(self.what)


The most important thing here is to understand that an aggregate command method,
such as ``make_it_so()`` above, should not do some work and then update the
attributes of the aggregate with the result of the work, but rather it should
trigger events with the results of the work, so that the events can be used
to update the state of the aggregate then and, importantly, each time the
aggregate is reconstructed from its events.

This aggregate class can be used without any infrastructure. Without
infrastructure however, there is no means of recovering the state of the
aggregate once the object goes out of scope.

.. code:: python

    # Call library factory method.
    world = World.__create__(ruler='gods')

    assert world.ruler == 'gods'

    # Execute commands.
    world.make_it_so('dinosaurs')
    world.make_it_so('trucks')

    # Assign attribute.
    world.ruler = 'money'

    assert world.history == ('dinosaurs', 'trucks'), world.history
    assert world.ruler == 'money'


Although every aggregate is a "little world", developing a more realistic
domain model would involve defining attributes, command methods, and domain
events particular to a concrete domain.

See the :doc:`Domain model documentation </topics/domainmodel>` for more
information about developing event-sourced domain models.


Configure environment
=====================

Generate cipher key (optional).

.. code:: python

    from eventsourcing.utils.random import encode_random_bytes

    # Keep this safe.
    cipher_key = encode_random_bytes(num_bytes=32)


Configure environment variables.

.. code:: python

    import os

    # Optional cipher key (random bytes encoded with Base64).
    os.environ['CIPHER_KEY'] = cipher_key

    # SQLAlchemy-style database connection string.
    os.environ['DB_URI'] = 'sqlite:///:memory:'


Run application
===============

With the library's application class
:class:`~eventsourcing.application.sqlalchemy.SQLAlchemyApplication`
instances of the ``World`` aggregate can persisted in the database
identified above using SQLAlchemy.

The code below demonstrates many of the features of the library,
such as optimistic concurrency control, data integrity, and
application-level encryption.

.. code:: python

    from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
    from eventsourcing.exceptions import ConcurrencyError

    # Construct simple application (used here as a context manager).
    with SQLAlchemyApplication(persist_event_type=World.Event) as app:

        # Call library factory method.
        world = World.__create__(ruler='gods')

        # Execute commands.
        world.make_it_so('dinosaurs')
        world.make_it_so('trucks')

        version = world.__version__ # note version at this stage
        world.make_it_so('internet')

        # Assign to event-sourced attribute.
        world.ruler = 'money'

        # View current state of aggregate.
        assert world.ruler == 'money'
        assert world.history[2] == 'internet'
        assert world.history[1] == 'trucks'
        assert world.history[0] == 'dinosaurs'

        # Publish pending events (to persistence subscriber).
        world.__save__()

        # Retrieve aggregate (replay stored events).
        copy = app.repository[world.id]
        assert isinstance(copy, World)

        # View retrieved state.
        assert copy.ruler == 'money'
        assert copy.history[2] == 'internet'
        assert copy.history[1] == 'trucks'
        assert copy.history[0] == 'dinosaurs'

        # Verify retrieved state (cryptographically).
        assert copy.__head__ == world.__head__

        # Discard aggregate.
        world.__discard__()
        world.__save__()

        # Discarded aggregate is not found.
        assert world.id not in app.repository
        try:
            # Repository raises key error.
            app.repository[world.id]
        except KeyError:
            pass
        else:
            raise Exception("Shouldn't get here")

        # Get historical state (at version from above).
        old = app.repository.get_entity(world.id, at=version)
        assert old.history[-1] == 'trucks' # internet not happened
        assert len(old.history) == 2
        assert old.ruler == 'gods'

        # Optimistic concurrency control (no branches).
        old.make_it_so('future')
        try:
            old.__save__()
        except ConcurrencyError:
            pass
        else:
            raise Exception("Shouldn't get here")

        # Check domain event data integrity (happens also during replay).
        events = app.event_store.list_events(world.id)
        last_hash = ''
        for event in events:
            event.__check_hash__()
            assert event.__previous_hash__ == last_hash
            last_hash = event.__event_hash__

        # Verify sequence of events (cryptographically).
        assert last_hash == world.__head__

        # Project application event notifications.
        from eventsourcing.application.notificationlog import NotificationLogReader
        reader = NotificationLogReader(app.notification_log)
        notifications = reader.read()
        notification_ids = [n['id'] for n in notifications]
        assert notification_ids == [1, 2, 3, 4, 5, 6]

        # Check records are encrypted (values not visible in database).
        record_manager = app.event_store.record_manager
        items = record_manager.get_items(world.id)
        for item in items:
            assert item.originator_id == world.id
            assert b'dinosaurs' not in item.state
            assert b'trucks' not in item.state
            assert b'internet' not in item.state


See the :doc:`Application documentation
</topics/application>` for more information about event-sourced applications,
and the :doc:`Infrastructure documentation
</topics/infrastructure>` for more information about infrastructure.
