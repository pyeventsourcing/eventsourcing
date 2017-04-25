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
object. Investigate the library class ``CassandraSettings`` for information about
configuring away from default settings.

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

        entity = app.create_new_example(foo='bar1')

        assert entity.id in app.example_repository

        assert app.example_repository[entity.id].foo == 'bar1'

        entity.foo = 'bar2'

        assert app.example_repository[entity.id].foo == 'bar2'

        # Discard the entity.
        entity.discard()
        assert entity.id not in app.example_repository

        try:
            app.example_repository[entity.id]
        except KeyError:
            pass
        else:
            raise Exception('KeyError was not raised')
