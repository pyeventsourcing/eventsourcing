===========
Quick start
===========

This section shows how to write a very simple event sourced
application using classes from the library. It shows the
general story, which is elaborated over the following pages.

Please use pip to install the library with the 'sqlalchemy' option.

::

    $ pip install eventsourcing[sqlalchemy]


Domain
======

Firstly, import the example entity class :class:`~eventsourcing.example.domainmodel.Example`
and its factory function :func:`~eventsourcing.example.domainmodel.create_new_example`.

.. code:: python

    from eventsourcing.example.domainmodel import create_new_example, Example


These classes will be used as the domain model in this example.

Infrastructure
==============

Next, setup an SQLite database in memory, using library classes
:class:`~eventsourcing.infrastructure.sqlalchemy.datastore.SQLAlchemyDatastore`, with
:class:`~eventsourcing.infrastructure.sqlalchemy.datastore.SQLAlchemySettings` and
:class:`~eventsourcing.infrastructure.sqlalchemy.activerecords.IntegerSequencedItemRecord`.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings, SQLAlchemyDatastore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import IntegerSequencedItemRecord

    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
        tables=(IntegerSequencedItemRecord,),
    )

    datastore.setup_connection()
    datastore.setup_tables()


Application
===========

Finally, define an application object factory, that constructs an application object from library
class :class:`~eventsourcing.application.base.ApplicationWithPersistencePolicies`.
The application class happens to take an active record strategy object and a session object.

The active record strategy is an instance of class
:class:`~eventsourcing.infrastructure.sqlalchemy.activerecords.SQLAlchemyActiveRecordStrategy`.
The session object is an argument of the application factory, and will be a normal
SQLAlchemy session object.

.. code:: python

    from eventsourcing.application.base import ApplicationWithPersistencePolicies
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.infrastructure.sequenceditem import SequencedItem
    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository

    def construct_application(session):
        app = ApplicationWithPersistencePolicies(
            entity_active_record_strategy=SQLAlchemyActiveRecordStrategy(
                active_record_class=IntegerSequencedItemRecord,
                session=session
            )
        )
        app.example_repository = EventSourcedRepository(
            event_store=app.entity_event_store,
        )
        return app

An example repository constructed from class
:class:`~eventsourcing.infrastructure.eventsourcedrepository.EventSourcedRepository`,
and is assigned to the application object attribute ``example_repository``. It is possible
to subclass the library application class, and extend it by constructing entity
repositories in the ``__init__()``, we just didn't do that here.


Run the code
============

Now, use the application to create, read, update, and delete "example" entities.

.. code:: python

    with construct_application(datastore.session) as app:

        # Create.
        example = create_new_example(foo='bar')

        # Read.
        assert example.id in app.example_repository
        assert app.example_repository[example.id].foo == 'bar'

        # Update.
        example.foo = 'baz'
        assert app.example_repository[example.id].foo == 'baz'

        # Delete.
        example.__discard__()
        assert example.id not in app.example_repository
