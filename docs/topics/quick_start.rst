===========
Quick start
===========

This section shows how to write a very simple event sourced
application using classes from the library. It shows the
general story, which is elaborated over the following pages.

Please use pip to install the library with the 'sqlalchemy' option.

::

    $ pip install eventsourcing[sqlalchemy]


Define model
============

Firstly, import the example entity class :class:`~eventsourcing.domain.model.aggregate.AggregateRoot`
and its factory function :func:`~eventsourcing.domain.model.decorators.attribute`.

The ``World`` aggregate is a subclass of ``AggregateRoot``. It has a read-only property called
``history``, and a mutatable attribute called ``ruler``. It has a command method called ``make_it_so``
which triggers a domain event called ``SomethingHappened``. And it has a nested domain event class
called ``SomethingHappened``.

.. code:: python

    from eventsourcing.domain.model.aggregate import AggregateRoot
    from eventsourcing.domain.model.decorators import attribute

    class World(AggregateRoot):

        def __init__(self, ruler=None, **kwargs):
            super(World, self).__init__(**kwargs)
            self._ruler = ruler
            self._history = []

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


Configure environment
=====================

Generate cipher key (optional).

.. code:: python

    from eventsourcing.utils.random import encode_random_bytes

    # Keep this safe.
    aes_cipher_key = encode_random_bytes(num_bytes=32)


Configure environment variables.

.. code:: python

    import os

    # Optional cipher key (random bytes encoded with Base64).
    os.environ['AES_CIPHER_KEY'] = aes_cipher_key

    # SQLAlchemy-style database connection string.
    os.environ['DB_URI'] = 'sqlite:///:memory:'
    # os.environ['DB_URI'] = 'mysql://username:password@localhost/eventsourcing'
    # os.environ['DB_URI'] = 'postgresql://username:password@localhost:5432/eventsourcing'


Run application
===============

Now, use the ``SimpleApplication`` to create, read, update, and delete ``World`` aggregates.

.. code:: python

    from eventsourcing.application.simple import SimpleApplication
    from eventsourcing.exceptions import ConcurrencyError

    # Construct simple application (used here as a context manager).
    with SimpleApplication() as app:

        # Call library factory method.
        world = World.__create__(ruler='god')

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

        # Repository raises key error (when aggregate not found).
        assert world.id not in app.repository
        try:
            app.repository[world.id]
        except KeyError:
            pass
        else:
            raise Exception("Shouldn't get here")

        # Get historical state (at version from above).
        old = app.repository.get_entity(world.id, at=version)
        assert old.history[-1].what == 'trucks' # internet not happened
        assert len(old.history) == 2
        assert old.ruler == 'god'

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

        # Check records are encrypted (values not visible in database).
        active_record_strategy = app.event_store.active_record_strategy
        items = active_record_strategy.get_items(world.id)
        for item in items:
            assert item.originator_id == world.id
            assert 'dinosaurs' not in item.state
            assert 'trucks' not in item.state
            assert 'internet' not in item.state
