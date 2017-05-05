==================
Alternative schema
==================

Stored event model
==================

The database schema we have been using so far stores events
in a sequence of "sequenced items", and the names in the
database schema reflect that design.

Let's say we want instead our database records to called "stored events".

It's easy to do. Just define a new sequenced item class,
e.g. ``StoredEvent`` below, and then supply a suitable
active record class. As before, create the table using the
new active record class, and pass both to the active record
strategy when constructing the application object.


.. code:: python

    from collections import namedtuple

    StoredEvent = namedtuple('StoredEvent', ['aggregate_id', 'aggregate_version', 'event_type', 'state'])


Then define a suitable active record class.

.. code:: python

    from sqlalchemy.ext.declarative.api import declarative_base
    from sqlalchemy.sql.schema import Column, Sequence, UniqueConstraint
    from sqlalchemy.sql.sqltypes import BigInteger, Integer, String, Text
    from sqlalchemy_utils import UUIDType

    Base = declarative_base()

    class StoredEventRecord(Base):
        # Explicit table name.
        __tablename__ = 'stored_events'

        # Unique constraint.
        __table_args__ = UniqueConstraint('aggregate_id', 'aggregate_version', name='stored_events_uc'),

        # Primary key.
        id = Column(Integer, Sequence('stored_event_id_seq'), primary_key=True)

        # Sequence ID (e.g. an entity or aggregate ID).
        aggregate_id = Column(UUIDType(), index=True)

        # Position (timestamp) of item in sequence.
        aggregate_version = Column(BigInteger(), index=True)

        # Type of the event (class name).
        event_type = Column(String(100))

        # State of the item (serialized dict, possibly encrypted).
        state = Column(Text())


Application and infrastructure
------------------------------

Then redefine the application class to use the new sequenced item and active record classes.


.. code:: python

    from eventsourcing.application.policies import PersistencePolicy
    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
    from eventsourcing.infrastructure.eventstore import EventStore
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
    from eventsourcing.infrastructure.sequenceditem import SequencedItem
    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
    from eventsourcing.example.domainmodel import Example, create_new_example


    class Application(object):
        def __init__(self, session):
            self.event_store = EventStore(
                active_record_strategy=SQLAlchemyActiveRecordStrategy(
                    session=session,
                    active_record_class=StoredEventRecord,
                    sequenced_item_class=StoredEvent,
                ),
                sequenced_item_mapper=SequencedItemMapper(
                    sequenced_item_class=StoredEvent,
                    sequence_id_attr_name='originator_id',
                    position_attr_name='originator_version',
                )
            )
            self.example_repository = EventSourcedRepository(
                event_store=self.event_store,
                mutator=Example._mutate,
            )
            self.persistence_policy = PersistencePolicy(self.event_store, event_type=Example.Event)

        def create_example(self, foo):
            return create_new_example(foo=foo)

        def close(self):
            self.persistence_policy.close()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()


Set up the database.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings, SQLAlchemyDatastore

    datastore = SQLAlchemyDatastore(
        base=Base,
        settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
        tables=(StoredEventRecord,),
    )

    datastore.setup_connection()
    datastore.setup_tables()


Run the code
------------

Then you can use the application to create, read, update,
and discard. And your events will be stored as "stored
events" rather than "sequenced items".

.. code:: python

    with Application(datastore.session) as app:

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
        assert example.id not in app.example_repository


Applause djangoevents project
=============================

It is possible to replace more aspects of the library, to make a more customized
application.
The excellent project `djangoevents <https://github.com/ApplauseOSS/djangoevents>`__
by `Applause <https://www.applause.com/>`__ is a Django app that provides a neat
way of taking an event sourcing approach in a Django project. It allows this library
to be used seamlessly with Django, by using the Django ORM to store events. Using
djangoevents is well documented in the README file. It adds some nice enhancements
to the capabilities of this library, and shows how various components can be
extended or replaced. Please note, the djangoevents project currently works with
a previous version of this library.
