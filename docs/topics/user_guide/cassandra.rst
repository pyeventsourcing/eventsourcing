===============
Using Cassandra
===============

Make sure you have a Cassandra server available on localhost at port 9042.

Install the library with the 'cassandra' option.

::

    pip install eventsourcing[cassandra]


Setup the connection and the database tables, using the library classes for Cassandra.

.. code:: python

    from eventsourcing.infrastructure.cassandra.datastore import CassandraSettings, CassandraDatastore
    from eventsourcing.infrastructure.cassandra.activerecords import CqlIntegerSequencedItem

    cassandra_datastore = CassandraDatastore(
        settings=CassandraSettings(),
        tables=(CqlIntegerSequencedItem,),
    )

    cassandra_datastore.setup_connection()
    cassandra_datastore.setup_tables()


The Cassandra application class below is similar to the example application class.
One difference is the Cassandra datastore object is not passed into the Cassandra
active record strategy.

You may investigate the ``CassandraSettings`` to learn how to configure
away from default settings.

.. code:: python

    from eventsourcing.infrastructure.cassandra.activerecords import CassandraActiveRecordStrategy
    from eventsourcing.application.policies import PersistencePolicy
    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
    from eventsourcing.infrastructure.eventstore import EventStore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.infrastructure.sequenceditem import SequencedItem
    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
    from eventsourcing.example.domainmodel import Example, create_new_example
    from eventsourcing.domain.model.events import VersionedEntityEvent


    class CassandraApplication(object):
        def __init__(self):
            self.event_store = EventStore(
                active_record_strategy=CassandraActiveRecordStrategy(
                    active_record_class=CqlIntegerSequencedItem,
                    sequenced_item_class=SequencedItem,
                ),
                sequenced_item_mapper=SequencedItemMapper(
                    sequenced_item_class=SequencedItem,
                    sequence_id_attr_name='originator_id',
                    position_attr_name='originator_version',
                )
            )
            self.example_repository = EventSourcedRepository(
                event_store=self.event_store,
                mutator=Example.mutate,
            )
            self.persistence_policy = PersistencePolicy(self.event_store, event_type=VersionedEntityEvent)

        def create_example(self, foo):
            return create_new_example(foo=foo)

        def close(self):
            self.persistence_policy.close()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()


The Cassandra application can be used in exactly the same way as the example application.

.. code:: python

    with CassandraApplication() as app:

        entity = app.create_example(foo='bar1')

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
