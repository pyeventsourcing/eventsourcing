==============
Infrastructure
==============

The library's infrastructure layer provides a cohesive mechanism for storing events as sequences of items.
The entire mechanism is encapsulated by the library's :class:`~eventsourcing.infrastructure.eventstore.EventStore`
class.

The event store uses a "sequenced item mapper" and an "active record strategy".
The sequenced item mapper and the active record strategy share a common "sequenced item" type.
The sequenced item mapper can convert objects such as domain events to sequenced items, and the active
record strategy can write sequenced items to a database.


Sequenced Items
===============

A sequenced item type provides a common persistence model across the components of
the mechanism. The sequenced item type is normally declared as a namedtuple.


.. code:: python

    from collections import namedtuple

    SequencedItem = namedtuple('SequencedItem', ['sequence_id', 'position', 'topic', 'data'])


The names of the fields are arbitrary. However, the first field of a sequenced item namedtuple represents
the identity of a sequence to which an item belongs, the second field represents the position of the item in its
sequence, the third field represents a topic to which the item pertains (dimension of concern), and the fourth
field represents the data associated with the item.


SequencedItem namedtuple
------------------------

The library provides a sequenced item namedtuple called
:class:`~eventsourcing.infrastructure.sequenceditem.SequencedItem`.


.. code:: python

    from eventsourcing.infrastructure.sequenceditem import SequencedItem


The attributes of ``SequencedItem`` are ``sequence_id``, ``position``, ``topic``, and ``data``.

The ``sequence_id`` identifies the sequence in which the item belongs.

The ``position`` identifies the position of the item in its sequence.

The ``topic`` identifies the dimension of concern to which the item pertains.

The ``data`` holds the values of the item, perhaps serialized to JSON, and optionally encrypted.


.. code:: python

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


StoredEvent namedtuple
----------------------

As an alternative, the library also provides a sequenced item namedtuple called ``StoredEvent``. The attributes of the
``StoredEvent`` namedtuple are ``originator_id``, ``originator_version``, ``event_type``, and ``state``.

The ``originator_id`` is the ID of the aggregate that published the event, and is equivalent to ``sequence_id`` above.

The ``originator_version`` is the version of the aggregate that published the event, and is equivalent to
``position`` above.

The ``event_type`` identifies the class of the domain event that is stored, and is equivalent to ``topic`` above.

The ``state`` holds the state of the domain event, and is equivalent to ``data`` above.


.. code:: python

    from eventsourcing.infrastructure.sequenceditem import StoredEvent

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


Active Record Strategy
======================

An active record strategy writes sequenced items to database records.

The library has an abstract base class ``AbstractActiveRecordStrategy`` with abstract methods ``append()`` and
``get_items()``, which can be used on concrete implementations to read and write sequenced items in a
database.

An active record strategy is constructed with a ``sequenced_item_class`` and a matching
``active_record_class``. The field names of a suitable active record class will match the field names of the
sequenced item namedtuple.


SQLAlchemy
----------

The library has a concrete active record strategy for SQLAlchemy provided by the object class
``SQLAlchemyActiveRecordStrategy``.


.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy


To help setup the database connection and tables, the library has object class ``SQLAlchemyDatastore``.


.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore


Database settings for ``SQLAlchemyDatastore`` can be configured using ``SQLAlchemySettings``,
which is constructed with a ``uri`` connection string. The code below uses an in-memory SQLite database.


.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings

    settings = SQLAlchemySettings(uri='sqlite:///:memory:')


The ``SQLAlchemyDatastore`` is constructed with the ``settings`` object,
and a tuple of active record classes passed using the ``tables`` arg.
The library provides active record classes for SQLAlchemy, such as ``IntegerSequencedItemRecord`` and
``StoredEventRecord``.

The ``IntegerSequencedItemRecord`` class matches the ``SequencedItem`` namedtuple, and the
``StoredEventRecord`` class matches the ``StoredEvent`` namedtuple. The code below uses ``StoredEventRecord``
with the ``StoredEvent`` namedtuple.


.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.activerecords import StoredEventRecord

    datastore = SQLAlchemyDatastore(
        settings=settings,
        tables=(StoredEventRecord,)
    )


Please note, if you have declared your own SQLAlchemy model ``Base`` class, you may wish to define your own active
record classes which inherit from your ``Base`` class. If so, if may help to refer to the library active record
classes to see how SQLALchemy ORM columns and indexes can be used to persist sequenced items.

The methods ``setup_connection()`` and ``setup_tables()`` of the datastore object
are used to setup the database connection and the tables.


.. code:: python

    datastore.setup_connection()
    datastore.setup_tables()


The ``SQLAlchemyActiveRecordStrategy`` also requires a scoped session object, passed using the constructor
arg ``session``. For convenience, the ``SQLAlchemyDatabase`` has a thread-scoped session facade set as its a
``session`` attribute. You may wish to use a different scoped session facade, such as a request-scoped session
object provided by a Web framework.


.. code:: python

    active_record_strategy = SQLAlchemyActiveRecordStrategy(
        sequenced_item_class=StoredEvent,
        active_record_class=StoredEventRecord,
        session=datastore.session,
    )


Sequenced items (or "stored events" in this example) can be appended to the database using the ``append()`` method
of the active record strategy.


.. code:: python

    active_record_strategy.append(stored_event1)


(Please note, since the position is given by the sequenced item itself, the word "append" means here "to add something
extra" rather than the perhaps more common but stricter meaning "to add to the end of a document". That is, the
database is deliberately not responsible for positioning a new item at the end of a sequence. So perhaps "save"
would be a better name for this operation.)

All the previously appended items of a sequence can be retrieved by using the ``get_items()`` method.


.. code:: python

    results = active_record_strategy.get_items(aggregate1)


Since by now only one item was stored, so there is only one item in the results.


.. code:: python

    assert len(results) == 1
    assert results[0] == stored_event1


Cassandra
---------

The library also has a concrete active record strategy for Apache Cassandra provided by
``CassandraActiveRecordStrategy`` class.

Similarly, for the ``CassandraActiveRecordStrategy``, the ``IntegerSequencedItemRecord``
from ``eventsourcing.infrastructure.cassandra.activerecords`` matches the ``SequencedItem`` namedtuple.
The ``StoredEventRecord`` from the same module matches the ``StoredEvent`` namedtuple.

The ``CassandraDatastore`` class uses the ``CassandraSettings`` class to setup a Cassandra database.


.. code:: python

    from eventsourcing.infrastructure.cassandra.datastore import CassandraDatastore, CassandraSettings
    from eventsourcing.infrastructure.cassandra.activerecords import CassandraActiveRecordStrategy, StoredEventRecord

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

    cassandra_datastore.drop_tables()
    cassandra_datastore.drop_connection()


Please refer to ``CassandraSettings`` class for information about configuring away from default settings.


Sequenced Item Mapper
=====================

A sequenced item mapper is used by the event store to map between sequenced item namedtuple
objects and application-level objects such as domain events.

The library provides a sequenced item mapper object class called ``SequencedItemMapper``.


.. code:: python

    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper


The method ``from_sequenced_item()`` can be used to convert sequenced item objects to application-level objects.


.. code:: python

    sequenced_item_mapper = SequencedItemMapper()

    domain_event = sequenced_item_mapper.from_sequenced_item(sequenced_item1)

    assert domain_event.sequence_id == sequence1
    assert domain_event.position == 0
    assert domain_event.foo == 'bar'


The method ``to_sequenced_item()`` can be used to convert application-level objects to sequenced item objects.


.. code:: python

    assert sequenced_item_mapper.to_sequenced_item(domain_event) == sequenced_item1


The ``SequencedItemMapper`` has a constructor arg ``sequenced_item_class``, which is by default the library's
``SequencedItem`` namedtuple.

If the names of the first two fields of the sequenced item namedtuple (e.g. ``sequence_id`` and ``position``) do not
match the names of the attributes of the application-level object which identify a sequence and a position in
the sequence (e.g. ``originator_id`` and ``originator_version``) then the attribute names can be
given to the sequenced item mapper using constructor args ``sequence_id_attr_name`` and ``position_attr_name``.

For example, in the code below, the domain event attribute names are given as ``'originator_id'`` and
``'originator_version'``.


.. code:: python

    sequenced_item_mapper = SequencedItemMapper(
        sequence_id_attr_name='originator_id',
        position_attr_name='originator_version'
    )

    domain_event1 = sequenced_item_mapper.from_sequenced_item(sequenced_item1)

    assert domain_event1.foo == 'bar', domain_event1
    assert domain_event1.originator_id == sequence1
    assert domain_event1.originator_version == 0
    assert sequenced_item_mapper.to_sequenced_item(domain_event1) == sequenced_item1


Alternatively, the constructor arg ``sequenced_item_class`` can be set with a sequenced item namedtuple type that is
different from the default ``SequencedItem`` namedtuple, such as the library's ``StoredEvent`` namedtuple.


.. code:: python

    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=StoredEvent,
    )

    domain_event1 = sequenced_item_mapper.from_sequenced_item(stored_event1)

    assert domain_event1.foo == 'bar', domain_event1
    assert domain_event1.originator_id == aggregate1
    assert sequenced_item_mapper.to_sequenced_item(domain_event1) == stored_event1


Which namedtuple you choose for your project depends on your preferences for the names
in the your persistence model. Since the alternative ``StoredEvent`` namedtuple can be used
instead of the default ``SequencedItem`` namedtuple, so it is possible to use a custom
namedtuple.


JSON Encoding
-------------

The ``SequencedItemMapper`` can be constructed with an optional ``json_encoder_class`` and
``json_decoder_class`` args. The defaults are the library's ``JSONObjectEncoder`` and
``JSONObjectDecoder`` which can be extended to support types that are not currently supported by the library.



Encryption
----------

The ``SequencedItemMapper`` can be constructed with an optional ``cipher`` object. The library provides
an AES cipher object class called ``AESCipher``.

The ``AESCipher`` is given an encryption key, using constructor arg ``aes_key``, which must be either 16, 24, or 32
random bytes (128, 192, or 256 bits). Longer keys take more time to encrypt plaintext, but produce more secure
ciphertext. Generating and storing a secure key requires functionality beyond the scope of this library.


.. code:: python

    from eventsourcing.infrastructure.cipher.aes import AESCipher

    cipher = AESCipher(aes_key=b'01234567890123456789012345678901')  # Key with 256 bits.

    ciphertext = cipher.encrypt('plaintext')
    plaintext = cipher.decrypt(ciphertext)

    assert ciphertext != 'plaintext'
    assert plaintext == 'plaintext'


If the ``SequencedItemMapper`` constructor arg ``always_encrypt`` is True, then
the ``state`` of the stored event will be encrypted.


.. code:: python

    # Construct sequenced item mapper to always encrypt domain events.
    ciphered_sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=StoredEvent,
        cipher=cipher,
        always_encrypt=True,
    )

    # Domain event attribute ``foo`` has value ``'bar'``.
    assert domain_event1.foo == 'bar'

    # Map the domain event to an encrypted stored event namedtuple.
    stored_event = ciphered_sequenced_item_mapper.to_sequenced_item(domain_event1)

    # Attribute names and values of the domain event are not visible in the encrypted ``state`` field.
    assert 'foo' not in stored_event.state
    assert 'bar' not in stored_event.state

    # Recover the domain event from the encrypted state.
    domain_event = ciphered_sequenced_item_mapper.from_sequenced_item(stored_event)

    # Domain event has decrypted attributes.
    assert domain_event.foo == 'bar'


Please note, the sequence ID and position values are necessarily not encrypted. However, by encrypting the state of
the event, sensitive information, such as personally identifiable information, will always be encrypted at the level
of the application, and so it will be encrypted in the database (and in all backups of the database).


Event Store
===========

The library's ``EventStore`` provides an interface to the library's cohesive mechanism for storing events as sequences
of items, and can be used directly within an event sourced application to append and retrieve its domain events.


.. code:: python

    from eventsourcing.infrastructure.eventstore import EventStore


The ``EventStore`` is constructed with a sequenced item mapper and an
active record strategy, both are discussed in detail in the sections above.


.. code:: python

    event_store = EventStore(
        sequenced_item_mapper=sequenced_item_mapper,
        active_record_strategy=active_record_strategy,
    )


The event store's method ``append()`` can append a domain event to its sequence. The event store uses the
``sequenced_item_mapper`` to obtain sequenced item namedtuples from domain events, and it uses the
``active_record_strategy`` to write the sequenced items to a database.

In the code below, a ``DomainEvent`` is appended to sequence ``aggregate1`` at position ``1``.


.. code:: python

    from eventsourcing.domain.model.events import DomainEvent

    event_store.append(
        DomainEvent(
            originator_id=aggregate1,
            originator_version=1,
            foo='baz',
        )
    )


The event store's method ``get_domain_events()`` is used to retrieve events that have previously been appended.
The event store uses the ``active_record_strategy`` to read the sequenced items from a database, and it
uses the ``sequenced_item_mapper`` to obtain domain events from the sequenced items.


.. code:: python

    results = event_store.get_domain_events(aggregate1)


Since by now two domain events have been stored, so there are two domain events in the results.


.. code:: python

    assert len(results) == 2

    assert results[0].originator_id == aggregate1
    assert results[0].foo == 'bar'

    assert results[1].originator_id == aggregate1
    assert results[1].foo == 'baz'


The optional arguments of ``get_domain_events()`` can be used to select some of the items in the sequence.

The ``lt`` arg is used to select items below the given position in the sequence.

The ``lte`` arg is used to select items below and at the given position in the sequence.

The ``gte`` arg is used to select items at and above the given position in the sequence.

The ``gt`` arg is used to select items above the given position in the sequence.

The ``limit`` arg is used to limit the number of items selected from the sequence.

The ``is_ascending`` arg is used when selecting items. It affects how any ``limit`` is applied, and determines the
order of the results. Hence, it can affect both the content of the results and the performance of the method.


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


Optimistic Concurrency Control
==============================

It is a feature of the infrastructure layer that it isn't possible to append two events at the same position in the
same sequence. This condition is coded as a concurrency error (since, by definition, a correct program running in a
single thread wouldn't attempt to append twice to the same position in the same sequence).


.. code:: python

    from eventsourcing.exceptions import ConcurrencyError

    # Fail to append an event at the same position in the same sequence as a previous event.
    try:
        event_store.append(
            DomainEvent(
                originator_id=aggregate1,
                originator_version=1,
                foo='baz',
            )
        )
    except ConcurrencyError:
        pass
    else:
        raise Exception("ConcurrencyError not raised")


This feature is implemented using optimistic concurrency control features of the underlying database. With
SQLAlchemy, the primary key constraint involves both the sequence and the position columns. With Cassandra
the "IF NOT EXISTS" feature is applied, whilst the position is the primary key in the sequence partition.


Timestamp Sequenced Events
==========================

The code above uses items that are sequenced by integer. As an alternative, items can be sequenced by timestamp.

Todo: More about timestamp sequenced events.


Snapshots
=========

Todo: More about snapshots.
