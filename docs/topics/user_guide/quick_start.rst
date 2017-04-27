===========
Quick start
===========

This section show how to write a working event sourced
application, using only a few lines of code.

Firstly, please use pip to install the library
with the 'sqlalchemy' option.

::

    pip install -U pip
    pip install eventsourcing[sqlalchemy]


Domain
======

Use the example entity class ``Example``, and its factory ``create_new_example``.

.. code:: python

    from eventsourcing.example.domainmodel import create_new_example, Example


Infrastructure
==============

Setup an SQLite database in memory, using library classes.

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

Construct an event sourced application object, with an example repository.

.. code:: python

    from eventsourcing.application.base import ApplicationWithPersistencePolicies
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.infrastructure.sequenceditem import SequencedItem
    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository

    def construct_application(session):
        app = ApplicationWithPersistencePolicies(
            integer_sequenced_active_record_strategy=SQLAlchemyActiveRecordStrategy(
                active_record_class=IntegerSequencedItemRecord,
                session=session
            )
        )
        app.example_repository = EventSourcedRepository(
            event_store=app.integer_sequenced_event_store,
            mutator=Example.mutate,
        )
        return app


Run the code
============

Use the application to create, read, update, and delete "example" entities.

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
        example.discard()
        assert entity.id not in app.example_repository
