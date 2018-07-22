===========
Quick start
===========

This section shows how to make a simple event sourced
application using classes from the library. It shows the
general story, which is elaborated over the following pages.

.. contents:: :local:

Please use pip to install the library with the 'sqlalchemy' option.

::

    $ pip install eventsourcing[sqlalchemy]


Define model
============

Define a domain model aggregate.

The class ``World`` defined below is a subclass of
:class:`~eventsourcing.domain.model.aggregate.AggregateRoot`.

The ``World`` has a property called ``history``. It also has an event sourced
attribute called ``ruler``.

It has a command method called ``make_it_so`` which triggers a domain event
of type ``SomethingHappened`` which is defined as a nested class.
The domain event class ``SomethingHappened`` has a ``mutate()`` method,
which happens to append triggered events to the history.

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
                obj._history.append(self)


This class can be used and completely tested without any infrastructure.

Although every aggregate is a "little world", developing a more realistic
domain model would involve defining attributes, command methods, and domain
events particular to a concrete domain.

Basically, you can understand everything if you understand that command methods,
such as ``make_it_so()`` in the example above, should not update the
state of the aggregate directly with the results of their work, but instead
trigger events using domain event classes which have ``mutate()`` methods
that can update the state of the aggregate using the values given to the
event when it was triggered. By refactoring the updating of the aggregate
state, from the command method, to a domain event object class, triggered
events can be stored and replayed to obtain persistent aggregates.


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

With the ``SimpleApplication`` from the library, you can create,
read, update, and delete ``World`` aggregates that are persisted
in the database identified above.

The code below demonstrates many of the features of the library,
such as optimistic concurrency control, data integrity, and
application-level encryption.


.. code:: python

    from eventsourcing.application.sqlalchemy import WithSQLAlchemy
    from eventsourcing.exceptions import ConcurrencyError

    # Construct simple application (used here as a context manager).
    with WithSQLAlchemy(persist_event_type=World.Event) as app:

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
        assert world.history[2].what == 'internet'
        assert world.history[1].what == 'trucks'
        assert world.history[0].what == 'dinosaurs'

        # Publish pending events (to persistence subscriber).
        world.__save__()

        # Retrieve aggregate (replay stored events).
        copy = app.repository[world.id]
        assert isinstance(copy, World)

        # View retrieved state.
        assert copy.ruler == 'money'
        assert copy.history[2].what == 'internet'
        assert copy.history[1].what == 'trucks'
        assert copy.history[0].what == 'dinosaurs'

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
        assert old.history[-1].what == 'trucks' # internet not happened
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
        events = app.event_store.get_domain_events(world.id)
        last_hash = ''
        for event in events:
            event.__check_hash__()
            assert event.__previous_hash__ == last_hash
            last_hash = event.__event_hash__

        # Verify sequence of events (cryptographically).
        assert last_hash == world.__head__

        # Project application event notifications.
        from eventsourcing.interface.notificationlog import NotificationLogReader
        reader = NotificationLogReader(app.notification_log)
        notifications = reader.read()
        notification_ids = [n['id'] for n in notifications]
        assert notification_ids == [1, 2, 3, 4, 5, 6]

        # Check records are encrypted (values not visible in database).
        record_manager = app.event_store.record_manager
        items = record_manager.get_items(world.id)
        for item in items:
            assert item.originator_id == world.id
            assert 'dinosaurs' not in item.state
            assert 'trucks' not in item.state
            assert 'internet' not in item.state
