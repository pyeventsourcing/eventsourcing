==============================
Optimistic concurrency control
==============================

Because of the unique constraint on the sequenced item table, it isn't
possible to branch the evolution of an entity and store two events
at the same version. Hence, if the entity you are working on has been
updated elsewhere, an attempt to update your object will raise a concurrency
exception.


Application and infrastructure
------------------------------

Setup infrastructure using library classes.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings, SQLAlchemyDatastore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import IntegerSequencedItemRecord

    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
        tables=(IntegerSequencedItemRecord,),
    )

    datastore.setup_connection()
    datastore.setup_tables()


Define a factory that uses library classes to construct an application object.

.. code:: python

    from eventsourcing.example.application import ExampleApplication
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.infrastructure.sequenceditem import SequencedItem

    def construct_example_application(session):
        active_record_strategy = SQLAlchemyActiveRecordStrategy(
            active_record_class=IntegerSequencedItemRecord,
            sequenced_item_class=SequencedItem,
            session=session
        )
        app = ExampleApplication(
            integer_sequenced_active_record_strategy=active_record_strategy
        )
        return app


Run the code
------------

Use the application to get two instances of the same entity, and try to change them independently.

.. code:: python

    from eventsourcing.exceptions import ConcurrencyError

    with construct_example_application(datastore.session) as app:

        entity = app.create_new_example(foo='bar1')

        a = app.example_repository[entity.id]
        b = app.example_repository[entity.id]

        # Change the entity using instance 'a'.
        a.foo = 'bar2'

        # Because 'a' has been changed since 'b' was obtained,
        # 'b' cannot be updated unless it is firstly refreshed.
        try:
            b.foo = 'bar3'
        except ConcurrencyError:
            pass
        else:
            raise Exception("Failed to control concurrency of 'b'.")

        # Refresh object 'b', so that 'b' has the current state of the entity.
        b = app.example_repository[entity.id]
        assert b.foo == 'bar2'

        # Changing the entity using instance 'b' now works because 'b' is up to date.
        b.foo = 'bar3'
        assert app.example_repository[entity.id].foo == 'bar3'

        # Now 'a' does not have the current state of the entity, and cannot be changed.
        try:
            a.foo = 'bar4'
        except ConcurrencyError:
            pass
        else:
            raise Exception("Failed to control concurrency of 'a'.")
