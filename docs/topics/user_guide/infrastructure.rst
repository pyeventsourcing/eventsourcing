==============
Infrastructure
==============

The library infrastructure layer implements the cohesive mechanism for storing events as sequenced items.

Events of different types can be mapped to a namedtuple, and the namedtuple can be used to create a database record.

Such database records can be selected and converted to namedtuples, and the namedtuples can be mapped to event object.


Stored Event
============

The library provides a namedtuple ``StoredEvent`` to which domain events can be mapped.

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

The library has an object class ``SequencedItemMapper``, which is used to map between events and namedtuples.

The method ``to_sequenced_item()`` is used to convert domain events to sequenced items.

The method ``from_sequenced_item()`` is used to convert sequenced items to domain events.


.. code:: python

    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper

    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=StoredEvent,
    )

    domain_event1 = sequenced_item_mapper.from_sequenced_item(stored_event1)

    assert domain_event1.foo == 'bar', domain_event1
    assert domain_event1.originator_id == aggregate1

    assert sequenced_item_mapper.to_sequenced_item(domain_event1) == stored_event1



Active Record Strategy
======================

Once a domain event has been converted to a stored event, it can be written to a datastore, according
to an active record strategy. Each active record strategy encapsulates a particular database, often using an active
record class to encapsulate individual database records.

The library provides classes that work with SQLAlchemy.


.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
    from eventsourcing.infrastructure.sqlalchemy.activerecords import StoredEventRecord

    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(),
        tables=(StoredEventRecord,)
    )
    datastore.setup_connection()
    datastore.setup_tables()


The library class ``SQLAlchemyActiveRecordStrategy`` method ``append()`` can be used to write a stored event into
a database. The method ``get_items()`` is used to retrieve stored events.


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


The method ``append()`` is used to append events.


.. code:: python

    from eventsourcing.domain.model.events import DomainEvent

    event2 = DomainEvent(
        originator_id=aggregate1,
        originator_version=1,
        foo='baz',
    )

    event_store.append(event2)

    result = event_store.get_domain_events(aggregate1)

    assert len(result) == 2, result
    assert result[1] == event2
