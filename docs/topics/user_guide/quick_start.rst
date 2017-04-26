===========
Quick start
===========

This section show how to write a working event sourced
application, using only a few lines of code.

Domain
======

Use the library's example domain model entity ``Example``, and factory ``create_new_example``.

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
        entity = create_new_example(foo='bar')

        # Read.
        assert entity.id in app.example_repository
        app.example_repository[entity.id].foo == 'bar'

        # Update.
        entity.foo = 'baz'
        app.example_repository[entity.id].foo == 'baz'

        # Delete.
        entity.discard()
        assert entity.id not in app.example_repository
