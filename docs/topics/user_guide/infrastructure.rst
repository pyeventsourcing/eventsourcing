==============
Infrastructure
==============

The library's infrastructure layer provides a cohesive mechanism for storing events as sequences of items.


Persistence Model
=================

When storing events, domain events of different types are mapped to a namedtuple, and the namedtuple is used to
create a database record.

The fields of the namedtuple define the persistence model for storing domain events. The field names of a
suitable database table will match the field names of the namedtuple. The database records can be
selected and converted to namedtuples, and the namedtuples can be mapped back to domain event objects.


SequencedItem
-------------

The library provides a namedtuple ``SequencedItem`` to which domain events can be mapped. The attributes of
``SequencedItem`` are ``sequence_id``, ``position``, ``topic``, and ``data``.

The ``sequence_id`` identifies the sequence in which the item belongs.

The ``position`` identifies the position of the item in its sequence.

The ``topic`` identifies the kind of the item that is stored.

The ``data`` holds the serialized values of the item that is stored.


.. code:: python

    from eventsourcing.infrastructure.sequenceditem import SequencedItem
    from uuid import uuid4


    sequence1 = uuid4()

    sequenced_item1 = SequencedItem(
        sequence_id=sequence1,
        position=0,
        topic='eventsourcing.domain.model.events#DomainEvent',
        data='{"foo":"bar"}'
    )

    assert sequenced_item1.sequence_id == sequence1
    assert sequenced_item1.position == 0
    assert sequenced_item1.topic == 'eventsourcing.domain.model.events#DomainEvent'
    assert sequenced_item1.data == '{"foo":"bar"}'


Stored Event
------------

As an alternative, the library also provides a namedtuple ``StoredEvent`` to which domain events can be mapped.
The attributes of ``StoredEvent`` are ``originator_id``, ``originator_version``, ``event_type``, and ``state``.

The ``originator_id`` is the ID of the aggregate that published the event, and is equivalent to the ``sequence_id``
above.

The ``originator_version`` is the version of the aggregate that published the event, and is equivalent to the
``position`` above.

The ``event_type`` identifies the class of the domain event that is stored, and is equivalent to ``topic`` above.

The ``state`` holds the serialized values of the attributes of the domain event, and is equivalent to ``data`` above.


.. code:: python

    from eventsourcing.infrastructure.sequenceditem import StoredEvent
    from uuid import uuid4


    aggregate1 = uuid4()

    stored_event1 = StoredEvent(
        originator_id=aggregate1,
        originator_version=0,
        event_type='eventsourcing.domain.model.events#DomainEvent',
        state='{"foo":"bar"}'
    )

    assert stored_event1.originator_id == aggregate1
    assert stored_event1.originator_version == 0
    assert stored_event1.event_type == 'eventsourcing.domain.model.events#DomainEvent'
    assert stored_event1.state == '{"foo":"bar"}'


Sequenced Item Mapper
=====================

The library has an object class ``SequencedItemMapper``, which is used to map between namedtuples and domain
events.

The method ``to_sequenced_item()`` is used to convert domain events to sequenced items.

The method ``from_sequenced_item()`` is used to convert sequenced items to domain events.

A namedtuple class is passed to the sequenced item mapper using constructor arg ``sequenced_item_class``. The default
value is ``SequencedItem``.



.. code:: python

    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
    from eventsourcing.domain.model.events import DomainEvent


    sequenced_item_mapper = SequencedItemMapper()

    domain_event = sequenced_item_mapper.from_sequenced_item(sequenced_item1)

    assert domain_event.foo == 'bar'
    assert domain_event.sequence_id == sequence1
    assert domain_event.position == 0
    assert isinstance(domain_event, DomainEvent)

    assert sequenced_item_mapper.to_sequenced_item(domain_event) == sequenced_item1


If the names of the domain event attributes that identify the sequence ID and the position
in the sequence do not correspond to the field names of the named tuple, the domain event's
attribute names can be passed to the sequenced item mapper, using
constructor args ``sequence_id_attr_name`` and ``position_attr_name``.


.. code:: python

    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
    from eventsourcing.domain.model.events import DomainEvent


    sequenced_item_mapper = SequencedItemMapper(
        sequence_id_attr_name='originator_id',
        position_attr_name='originator_version'
    )

    domain_event1 = sequenced_item_mapper.from_sequenced_item(sequenced_item1)

    assert domain_event1.foo == 'bar', domain_event1
    assert domain_event1.originator_id == sequence1
    assert domain_event1.originator_version == 0
    assert isinstance(domain_event1, DomainEvent)
    assert sequenced_item_mapper.to_sequenced_item(domain_event1) == sequenced_item1


An alternative is to use a namedtuple with fields that correspond to the
domain event attribute names, such as the ``StoredEvent`` namedtuple (discussed above).

.. code:: python

    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper
    from eventsourcing.domain.model.events import DomainEvent


    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=StoredEvent,
    )

    domain_event1 = sequenced_item_mapper.from_sequenced_item(stored_event1)

    assert domain_event1.foo == 'bar', domain_event1
    assert domain_event1.originator_id == aggregate1
    assert isinstance(domain_event1, DomainEvent)
    assert sequenced_item_mapper.to_sequenced_item(domain_event1) == stored_event1


Which namedtuple you choose for your project depends on your preferences for the names
in the database schema: if you want the names to resemble the attributes of domain event
classes in the library, then use the ``StoredEvent`` namedtuple. Otherwise, use the
``SequencedItem`` namedtuple, or define a namedtuple that more closely suits your purpose.


Active Record Strategy
======================

An active record strategy writes namedtuples to database records.

The library has an abstract base class ``AbstractActiveRecordStrategy``. The method ``append()`` can
be used to write namedtuples into the database. The method ``get_items()`` is used to
read namedtuples from the database.

Each active record strategy requires a ``sequenced_item_class`` and a matching ``active_record_class``.

The library has a concrete active record strategy for SQLAlchemy provided by the object class
``SQLAlchemyActiveRecordStrategy``, and one for Apache Cassandra provided by ``CassandraActiveRecordStrategy``.
The library also provides various active record classes for SQLAlchemy and for Cassandra.

To help setup database connection and tables for these two active record strategies, the library has object classes
``SQLAlchemyDatastore`` and ``CassandraDatastore``. Database settings can be configured using either
``SQLAlchemySettings`` or ``CassandraSettings``.


SQLAlchemy
----------

The ``SQLAlchemyDatastore`` is used to setup an SQLAlchemy database, and requires a ``settings`` object,
and a tuple of active record classes passed using the ``tables`` arg.

For the ``SQLAlchemyActiveRecordStrategy``, the ``IntegerSequencedItemRecord``
from ``eventsourcing.infrastructure.sqlalchemy.activerecords`` matches the ``SequencedItem`` namedtuple.

The ``StoredEventRecord`` from the same module matches the ``StoredEvent`` namedtuple.

Note, if you have declared your own SQLAlchemy model ``Base`` class, you may wish to define your own active
record classes which inherit from your ``Base`` class. If so, if may help to refer to the library active record
classes to see which fields are required, and how to setup the indexes.

The code below uses the ``StoredEventRecord`` to setup a table suitable for storing the ``StoredEvent`` namedtuple.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
    from eventsourcing.infrastructure.sqlalchemy.activerecords import StoredEventRecord

    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(),
        tables=(StoredEventRecord,)
    )
    datastore.setup_connection()
    datastore.setup_tables()


The ``SQLAlchemyActiveRecordStrategy`` also requires a scoped session object to be passed, using the ``session`` arg.


.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy

    active_record_strategy = SQLAlchemyActiveRecordStrategy(
        sequenced_item_class=StoredEvent,
        active_record_class=StoredEventRecord,
        session=datastore.session,
    )


After setting up the connection and the tables, stored events can be appended to the database using the active
record strategy object.


.. code:: python

    active_record_strategy.append(stored_event1)


Stored events previously appended to the database can be retrieved using the sequence or aggregate ID.


.. code:: python

    results = active_record_strategy.get_items(aggregate1)

    assert results[0] == stored_event1


Cassandra
---------

Similarly, for the ``CassandraActiveRecordStrategy``, the ``IntegerSequencedItemRecord``
from ``eventsourcing.infrastructure.cassandra.activerecords`` matches the ``SequencedItem`` namedtuple.
The ``StoredEventRecord`` from the same module matches the ``StoredEvent`` namedtuple.


.. code:: python

    from eventsourcing.infrastructure.cassandra.datastore import CassandraDatastore, CassandraSettings
    from eventsourcing.infrastructure.cassandra.activerecords import StoredEventRecord
    from eventsourcing.infrastructure.cassandra.activerecords import CassandraActiveRecordStrategy

    cassandra_datastore = CassandraDatastore(
        settings=CassandraSettings(),
        tables=(StoredEventRecord,)
    )
    cassandra_datastore.setup_connection()
    cassandra_datastore.setup_tables()


    cassandra_active_record_strategy = CassandraActiveRecordStrategy(
        active_record_class=StoredEventRecord,
        sequenced_item_class=StoredEvent,
    )

    results = cassandra_active_record_strategy.get_items(aggregate1)

    assert len(results) == 0

    cassandra_active_record_strategy.append(stored_event1)

    results = cassandra_active_record_strategy.get_items(aggregate1)

    assert results[0] == stored_event1


Event Store
===========

The event store is used by other objects to append and retrieve domain events.

The library object class ``EventStore`` is constructed with a ``sequenced_item_mapper`` and an
``active_record_strategy``.


.. code:: python

    from eventsourcing.infrastructure.eventstore import EventStore


    event_store = EventStore(
        sequenced_item_mapper=sequenced_item_mapper,
        active_record_strategy=active_record_strategy,
    )


The method ``append()`` is used to append events. If a second event is appended to the same
sequence, the sequence will then have two events.


.. code:: python

    event2 = DomainEvent(
        originator_id=aggregate1,
        originator_version=1,
        foo='baz',
    )

    event_store.append(event2)


The method ``get_domain_events()`` is used to retrieve events.


.. code:: python

    result = event_store.get_domain_events(aggregate1)

    assert len(result) == 2, result

    assert result[0].originator_id == aggregate1
    assert result[0].foo == 'bar'

    assert result[1].originator_id == aggregate1
    assert result[1].foo == 'baz'


Optional arguments of ``get_domain_events`` can be used to select some of the item in the sequence.

The ``lt`` arg is used to select items below the given position in the sequence.

The ``lte`` arg is used to select items below and at the given position in the sequence.

The ``gte`` arg is used to select items at and above the given position in the sequence.

The ``lte`` arg is used to select items above the given position in the sequence.

The ``limit`` arg is used to limit the number of items selected from the sequence.

The ``is_ascending`` arg is used when selecting items. It affects how the query is performed, determines the order of
the results, and affects how any ``limit`` is applied. Hence, it can affect both the results and the performance of
the method.

.. code:: python

    # Get events below and at position 0.
    result = event_store.get_domain_events(aggregate1, lte=0)
    assert len(result) == 1, result
    assert result[0].originator_id == aggregate1
    assert result[0].originator_version == 0
    assert result[0].foo == 'bar'

    # Get events at and above position 1.
    result = event_store.get_domain_events(aggregate1, gte=1)
    assert len(result) == 1, result
    assert result[0].originator_id == aggregate1
    assert result[0].originator_version == 1
    assert result[0].foo == 'baz'

    # Get the first event in the sequence.
    result = event_store.get_domain_events(aggregate1, limit=1)
    assert len(result) == 1, result
    assert result[0].originator_id == aggregate1
    assert result[0].originator_version == 0
    assert result[0].foo == 'bar'

    # Get the last event in the sequence.
    result = event_store.get_domain_events(aggregate1, limit=1, is_ascending=False)
    assert len(result) == 1, result
    assert result[0].originator_id == aggregate1
    assert result[0].originator_version == 1
    assert result[0].foo == 'baz'
