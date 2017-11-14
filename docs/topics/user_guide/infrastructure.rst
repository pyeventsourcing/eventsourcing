==============
Infrastructure
==============

The library infrastructure layer implements the cohesive mechanism for storing events as sequenced items.

When storing events, domain events of different types are mapped to a namedtuple, and the namedtuple is used to
create a database record. Such database records can be selected and converted to namedtuples, and the namedtuples
can be mapped back to event objects.

The fields of the namedtuple define the persistence model for storing domain events. The field names of the database
record are expected to follow the field names of the namedtuple.


SequencedItem
=============

The library provides a namedtuple ``SequencedItem`` to which domain events can be mapped.

The attributes of ``SequencedItem`` are ``sequence_id``, ``position``, ``topic``, and ``data``.

The ``sequence_id`` identifies in which sequence the stored event belongs.

The ``position`` identifies the position in that sequence.

The ``topic`` identifies the particular type of the domain event that is stored.

The ``data`` holds the serialized values of the attributes of the domain event.


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


Stored Event
============

As an alternative, the library also provides a namedtuple ``StoredEvent`` to which domain events can be mapped.

The attributes of ``StoredEvent`` are ``originator_id``, ``originator_version``, ``event_type``, and ``state``.

The ``originator_id`` identifies in which sequence the stored event belongs. The ``originator_version`` identifies
the position in that sequence.

The ``event_type`` identifies the particular type of the domain event that is stored.

The ``state`` holds the serialized values of the attributes of the domain event.


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


Sequenced Item Mapper
=====================

The library has an object class ``SequencedItemMapper``, which is used to map between domain events and namedtuples.

A namedtuple class is passed to the sequenced item mapper using constructor arg ``sequenced_item_class``. The default
value is ``SequencedItem``.

The method ``to_sequenced_item()`` is used to convert domain events to sequenced items.

The method ``from_sequenced_item()`` is used to convert sequenced items to domain events.



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
in the sequence do not correspond to the field names of the named tuple, the attribute names
of the domain event can be passed to the sequenced item mapper, using
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


A more straightforward approach is to use a namedtuple with fields that correspond to the
domain event attribute names, such as the ``StoredEvent`` namedtuple.


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



Active Record Strategy
======================

An active record strategy writes namedtuples to database records.

Each active record strategy encapsulates a particular database, often using an active
record class to encapsulate individual database records.

The library has an abstract base class ``AbstractActiveRecordStrategy``, and active record
strategies for SQLAlchemy and Cassandra, ``SQLAlchemyActiveRecordStrategy`` and ``CassandraActiveRecordStrategy``.

To help setup database connection and tables, the library has object classes ``SQLAlchemyDatastore``
and ``CassandraDatastore``.


.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
    from eventsourcing.infrastructure.sqlalchemy.activerecords import StoredEventRecord

    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(),
        tables=(StoredEventRecord,)
    )
    datastore.setup_connection()
    datastore.setup_tables()


The method ``append()`` of the active record strategy can be used to write namedtuples into
the database. The method ``get_items()`` is used to read namedtuples from the database.


.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy


    active_record_strategy = SQLAlchemyActiveRecordStrategy(
        session=datastore.session,
        active_record_class=StoredEventRecord,
        sequenced_item_class=StoredEvent,
    )

    active_record_strategy.append(stored_event1)

    results = active_record_strategy.get_items(aggregate1)

    assert results[0] == stored_event1



Event Store
===========

The library object class ``EventStore`` is used to append and retrieve domain events.

The event store is constructed with an active record strategy and a sequenced item mapper.


.. code:: python

    from eventsourcing.infrastructure.eventstore import EventStore


    event_store = EventStore(
        sequenced_item_mapper=sequenced_item_mapper,
        active_record_strategy=active_record_strategy,
    )


The method ``get_domain_events()`` is used to retrieve events.


.. code:: python

    result = event_store.get_domain_events(aggregate1)

    assert len(result) == 1, result

    assert result[0].originator_id == aggregate1
    assert result[0].foo == 'bar'


The method ``append()`` is used to append events. If a second event is appended to the
sequence, the sequence will then have two events.


.. code:: python

    event2 = DomainEvent(
        originator_id=aggregate1,
        originator_version=1,
        foo='baz',
    )

    event_store.append(event2)

    result = event_store.get_domain_events(aggregate1)

    assert len(result) == 2, result
    assert result[1] == event2
