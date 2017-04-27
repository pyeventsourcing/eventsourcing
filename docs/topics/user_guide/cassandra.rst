===============
Using Cassandra
===============

Make sure you have a Cassandra server available on localhost at port 9042.

Install the library with the 'cassandra' option.

::

    pip install eventsourcing[cassandra]


Infrastructure
--------------

Setup the connection and the database tables, using the library classes for Cassandra.

Investigate the library class ``CassandraSettings`` for information about
configuring away from default settings.

.. code:: python

    from eventsourcing.infrastructure.cassandra.datastore import CassandraSettings, CassandraDatastore
    from eventsourcing.infrastructure.cassandra.activerecords import IntegerSequencedItemRecord

    cassandra_datastore = CassandraDatastore(
        settings=CassandraSettings(),
        tables=(IntegerSequencedItemRecord,),
    )

    cassandra_datastore.setup_connection()
    cassandra_datastore.setup_tables()


Application object
------------------

Define a factory that uses library classes for Cassandra to construct an application
object.

.. code:: python

    from eventsourcing.example.application import ExampleApplication
    from eventsourcing.infrastructure.cassandra.activerecords import CassandraActiveRecordStrategy

    def construct_application():
        active_record_strategy = CassandraActiveRecordStrategy(
            active_record_class=IntegerSequencedItemRecord,
        )
        app = ExampleApplication(
            integer_sequenced_active_record_strategy=active_record_strategy,
        )
        return app


Run the code
------------

The example application can be used in the same way as before.

.. code:: python

    with construct_application() as app:

        # Create.
        example = app.create_new_example(foo='bar')

        # Read.
        assert example.id in app.example_repository
        assert app.example_repository[example.id].foo == 'bar'

        # Update.
        example.foo = 'baz'
        assert app.example_repository[example.id].foo == 'baz'

        # Delete.
        example.discard()
        assert example.id not in app.example_repository
