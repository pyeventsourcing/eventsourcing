==============
Infrastructure
==============

The library's infrastructure layer provides a cohesive
mechanism for storing events as sequences of items.

The entire mechanism is encapsulated by the library's
:class:`~eventsourcing.infrastructure.eventstore.EventStore`
class. The event store uses a "sequenced item mapper" and an
"active record strategy". The sequenced item mapper and the
active record strategy share a common "sequenced item" type.
The sequenced item mapper can convert objects such as domain
events to sequenced items, and the active record strategy can
write sequenced items to a database.

.. contents:: :local:


Sequenced items
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
        data='{"foo":"bar"}',
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
        state='{"foo":"bar"}',
    )
    assert stored_event1.originator_id == aggregate1
    assert stored_event1.originator_version == 0
    assert stored_event1.event_type == 'eventsourcing.domain.model.events#DomainEvent'
    assert stored_event1.state == '{"foo":"bar"}'


Active record strategies
========================

An active record strategy writes sequenced items to database records.

The library has an abstract base class ``AbstractActiveRecordStrategy`` with abstract methods ``append()`` and
``get_items()``, which can be used on concrete implementations to read and write sequenced items in a
database.

An active record strategy is constructed with a ``sequenced_item_class`` and a matching
``active_record_class``. The field names of a suitable active record class will match the field names of the
sequenced item namedtuple.


SQLAlchemy
----------

To run the examples below, please install the library with the
'sqlalchemy' option.

.. code::

    $ pip install eventsourcing[sqlalchemy]


The library has a concrete active record strategy for SQLAlchemy provided by the object class
``SQLAlchemyActiveRecordStrategy``.


.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy


The library also provides active record classes for SQLAlchemy, such as ``IntegerSequencedItemRecord`` and
``StoredEventRecord``. The ``IntegerSequencedItemRecord`` class matches the default ``SequencedItem``
namedtuple. The ``StoredEventRecord`` class matches the alternative ``StoredEvent`` namedtuple.
There is also a ``TimestampSequencedItemRecord`` and a ``SnapshotRecord``.

The code below uses the namedtuple ``StoredEvent`` and the active record ``StoredEventRecord``.


.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.activerecords import StoredEventRecord


Database settings can be configured using ``SQLAlchemySettings``, which is constructed with a ``uri`` connection
string. The code below uses an in-memory SQLite database.


.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings

    settings = SQLAlchemySettings(uri='sqlite:///:memory:')


To help setup a database connection and tables, the library has object class ``SQLAlchemyDatastore``.

The ``SQLAlchemyDatastore`` is constructed with the ``settings`` object,
and a tuple of active record classes passed using the ``tables`` arg.


.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore

    datastore = SQLAlchemyDatastore(
        settings=settings,
        tables=(StoredEventRecord,)
    )


Please note, if you have declared your own SQLAlchemy model ``Base`` class, you may wish to define your own active
record classes which inherit from your ``Base`` class. If so, if may help to refer to the library active record
classes to see how SQLALchemy ORM columns and indexes can be used to persist sequenced items.

The methods ``setup_connection()`` and ``setup_tables()`` of the datastore object
can be used to setup the database connection and the tables.


.. code:: python

    datastore.setup_connection()
    datastore.setup_tables()


As well as ``sequenced_item_class`` and a matching ``active_record_class``, the ``SQLAlchemyActiveRecordStrategy``
requires a scoped session object, passed using the constructor arg ``session``. For convenience, the
``SQLAlchemyDatabase`` has a thread-scoped session facade set as its a ``session`` attribute. You may
wish to use a different scoped session facade, such as a request-scoped session object provided by a Web
framework.

With the database setup, the ``SQLAlchemyActiveRecordStrategy`` can be constructed,
and used to store events using SQLAlchemy.


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

    results = active_record_strategy.list_items(aggregate1)


Since by now only one item was stored, so there is only one item in the results.


.. code:: python

    assert len(results) == 1
    assert results[0] == stored_event1


SQLAlchemy Dialects
~~~~~~~~~~~~~~~~~~~

The databases supported by core `SQLAlchemy dialects <http://docs.sqlalchemy.org/en/latest/dialects/>`
are Firebird, Microsoft SQL Server, MySQL, Oracle, PostgreSQL, SQLite, and Sybase. This library's
infrastructure classes for SQLAlchemy have been tested with MySQL, PostgreSQL, and SQLite.

MySQL
~~~~~

For MySQL, the Python package `mysqlclient <https://pypi.python.org/pypi/mysqlclient>`__
can be used.

.. code::

    $ pip install mysqlclient

The ``uri`` for MySQL would look something like this.

.. code::

    mysql://username:password@localhost/eventsourcing


PostgreSQL
~~~~~~~~~~

For PostgreSQL, the Python package `psycopg2 <https://pypi.python.org/pypi/psycopg2>`__
can be used.

.. code::

    $ pip install psycopg2

The ``uri`` for PostgreSQL would look something like this.

.. code::

    postgresql://username:password@localhost:5432/eventsourcing


SQLite
~~~~~~

SQLite is shipped with core Python packages, so nothing extra needs to be installed.

The ``uri`` for a temporary SQLite database might look something like this.

.. code::

    sqlite:::////tmp/eventsourcing.db


Please note, the library's SQLAlchemy insfrastructure defaults to using
an in memory SQLite database, which is the fastest way to run the library,
and is recommended as a convenience for development.


Django ORM
----------

The library also has a concrete active record strategy for the Django ORM provided by
``DjangoActiveRecordStrategy`` class.

To run the examples below, please install the library with the
'django' option.

.. code::

    $ pip install eventsourcing[django]


For the ``DjangoActiveRecordStrategy``, the ``IntegerSequencedItemRecord``
from ``eventsourcing.infrastructure.django.models`` matches the ``SequencedItem``
namedtuple. The ``StoredEventRecord`` from the same module matches the ``StoredEvent``
namedtuple. There is also a ``TimestampSequencedItemRecord`` and a ``SnapshotRecord``.

The package ``eventsourcing.infrastructure.django`` is a Django application. To include
these models in your Django project, either include the application by name in your list
of ``INSTALLED_APPS``, or import the classes you want into one of your application's ``models.py``.

.. code:: python

    INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'eventsourcing.infrastructure.django'
    ]


The library has a little Django project for testing the app, it used here to help run the app.

.. code:: python

    import os
    os.environ['DJANGO_SETTINGS_MODULE'] = 'eventsourcing.tests.djangoproject.djangoproject.settings'


Having setup the environment, before running the example below, we need to setup Django.

.. code:: python

    import django

    django.setup()


Before using the database, make the migrations have been applied. If you import
the classes into your own application, you will firstly need to ``makemigrations``.
Otherwise, the application at ``eventsourcing.infrastructure.django`` has migrations
that will add four tables, one for each of the sequenced item active record classes
mentioned above.

.. code::

    $ python manage.py migrate

An alternative to using the ``manage.py`` command line interface is using the
``call_command()`` function, provided by Django.

.. code:: python

    from django.core.management import call_command

    call_command('migrate')


With the database setup, the ``DjangoActiveRecordStrategy`` can be constructed,
and used to store events using the Django ORM.

.. code:: python

    from eventsourcing.infrastructure.django.activerecords import DjangoActiveRecordStrategy
    from eventsourcing.infrastructure.django.models import StoredEventRecord


    django_active_record_strategy = DjangoActiveRecordStrategy(
        active_record_class=StoredEventRecord,
        sequenced_item_class=StoredEvent,
    )

    results = django_active_record_strategy.list_items(aggregate1)
    assert len(results) == 0

    django_active_record_strategy.append(stored_event1)

    results = django_active_record_strategy.list_items(aggregate1)
    assert results[0] == stored_event1


Please note, if you want to use the Django ORM as infrastructure for
an event sourced application, the you can use the application classes
in the :doc:`application </topcis/application>` section of this documentation.

When it comes to deployment, just remember that you need only one
instance of the application in any given process, otherwise subscribers
will be registered too many times. There are perhaps three different
processes to consider. Firstly, running the test suite for your Django
project. Secondly, running the Django project with WSGI (or equivalent).
Thirdly, running the Django project from a task queue worker, such as RabbitMQ.

For the first case, it is recommended either to have a base test case class,
which initialises the application during ``setUp()`` and closes the application
during ``tearDown()``. Another option is to use a generator fixtures in pytest.
Just make sure the application is constructed and then closed, for each test if
necessary, otherwise for the whole suite. Tests can then get the application
object freely.

For the second case, it is recommended to construct the application object from
the project's ``wsgi.py`` file, which doesn't get used when running Django from a test suite,
or from a task queue worker. Views can then get the application object freely.
Closing the application doesn't matter, because it will be used until the process
ends.

For the third case, it is recommended to construct the application in a suitable
signal from the task queue framework, so that the application is constructed
before request threads begin. Jobs can then get the application object freely.
Closing the application doesn't matter, because it will be used until the process
ends.

In each case, to make things very clear for others, it is recommended to construct
the application object with a module level function called ``init_application()``
that assigns to a module level variable, and then obtain the application object with
another module level function called ``get_application()``, which raises an exception
if the application has not been constructed. See the
:doc:`deployment </topics/deployment>` section for more information.


Django Backends
~~~~~~~~~~~~~~~

The supported `Django backends <https://docs.djangoproject.com/en/2.0/ref/databases/>`
are PostgreSQL, MySQL, SQLite, and Oracle. This library's Django infrastructure classes
have been tested with PostgreSQL, MySQL, SQLite.


Apache Cassandra
----------------

To run the examples below, please install the library with the
'cassandra' option.

.. code::

    $ pip install eventsourcing[cassandra]


The library also has a concrete active record strategy for Apache Cassandra provided by
``CassandraActiveRecordStrategy`` class.

For the ``CassandraActiveRecordStrategy``, the ``IntegerSequencedItemRecord``
from ``eventsourcing.infrastructure.cassandra.activerecords`` matches the ``SequencedItem``
namedtuple. The ``StoredEventRecord`` from the same module matches the ``StoredEvent``
namedtuple.  There is also a ``TimestampSequencedItemRecord`` and a ``SnapshotRecord``.

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

    results = cassandra_active_record_strategy.list_items(aggregate1)
    assert len(results) == 0

    cassandra_active_record_strategy.append(stored_event1)

    results = cassandra_active_record_strategy.list_items(aggregate1)
    assert results[0] == stored_event1

    cassandra_datastore.drop_tables()
    cassandra_datastore.close_connection()


The ``CassandraDatastore`` and ``CassandraSettings`` are be used in the same was as
``SQLAlchemyDatastore`` and ``SQLAlchemySettings`` above. Please investigate
library class :class:`~eventsourcing.infrastructure.cassandra.datastore.CassandraSettings`
for information about configuring away from default settings.


Sequenced item conflicts
------------------------

It is a common feature of the active record strategy classes that it isn't possible successfully
to append two items at the same position in the same sequence. If such an attempt is made, a
``SequencedItemConflict`` will be raised.

.. code:: python

    from eventsourcing.exceptions import SequencedItemConflict

    # Fail to append an item at the same position in the same sequence as a previous item.
    try:
        active_record_strategy.append(stored_event1)
    except SequencedItemConflict:
        pass
    else:
        raise Exception("SequencedItemConflict not raised")


This feature is implemented using optimistic concurrency control features of the underlying database. With
SQLAlchemy, a unique constraint is used that involves both the sequence and the position columns.
The Django ORM strategy works in the same way.

With Cassandra the position is the primary key in the sequence partition, and the "IF NOT
EXISTS" feature is applied. The Cassandra database management system implements the Paxos
protocol, and can thereby accomplish linearly-scalable distributed optimistic concurrency
control, guaranteeing sequential consistency of the events of an entity despite the database
being distributed. It is also possible to serialize calls to the methods of an entity, but
that is out of the scope of this package — if you wish to do that, perhaps something like
`Zookeeper <https://zookeeper.apache.org/>`__ might help.



Sequenced item mapper
=====================

A sequenced item mapper is used by the event store to map between sequenced item namedtuple
objects and application-level objects such as domain events.

The library provides a sequenced item mapper object class called ``SequencedItemMapper``.


.. code:: python

    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper


The ``SequencedItemMapper`` has a constructor arg ``sequenced_item_class``, which defaults to the library's
sequenced item namedtuple ``SequencedItem``.


.. code:: python

    sequenced_item_mapper = SequencedItemMapper()


The method ``from_sequenced_item()`` can be used to convert sequenced item objects to application-level objects.


.. code:: python

    domain_event = sequenced_item_mapper.from_sequenced_item(sequenced_item1)

    assert domain_event.foo == 'bar'


The method ``to_sequenced_item()`` can be used to convert application-level objects to sequenced item namedtuples.


.. code:: python

    assert sequenced_item_mapper.to_sequenced_item(domain_event).data == sequenced_item1.data


If the names of the first two fields of the sequenced item namedtuple (e.g. ``sequence_id`` and ``position``) do not
match the names of the attributes of the application-level object which identify a sequence and a position (e.g.
``originator_id`` and ``originator_version``) then the attribute names can be given to the sequenced item mapper
using constructor args ``sequence_id_attr_name`` and ``position_attr_name``.


.. code:: python

    from eventsourcing.domain.model.events import DomainEvent

    domain_event1 = DomainEvent(
        originator_id=aggregate1,
        originator_version=1,
        foo='baz',
    )

    sequenced_item_mapper = SequencedItemMapper(
        sequence_id_attr_name='originator_id',
        position_attr_name='originator_version'
    )


    assert domain_event1.foo == 'baz'

    assert sequenced_item_mapper.to_sequenced_item(domain_event1).sequence_id == aggregate1


Alternatively, the constructor arg ``sequenced_item_class`` can be set with a sequenced item namedtuple type that is
different from the default ``SequencedItem`` namedtuple, such as the library's ``StoredEvent`` namedtuple.


.. code:: python

    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=StoredEvent
    )

    domain_event1 = sequenced_item_mapper.from_sequenced_item(stored_event1)

    assert domain_event1.foo == 'bar', domain_event1


Since the alternative ``StoredEvent`` namedtuple can be used instead of the default
``SequencedItem`` namedtuple, so it is possible to use a custom namedtuple.
Which alternative you use for your project depends on your preferences for the names
in the your domain events and your persistence model.

Please note, it is required of these application-level objects that the  "topic" generated by
``get_topic()`` from the object class is resolved by ``resolve_topic()`` back to the same object class.


.. code:: python

    from eventsourcing.domain.model.events import Created
    from eventsourcing.utils.topic import get_topic, resolve_topic

    topic = get_topic(Created)
    assert resolve_topic(topic) == Created
    assert topic == 'eventsourcing.domain.model.events#Created'


Custom JSON transcoding
-----------------------

The ``SequencedItemMapper`` can be constructed with optional args ``json_encoder_class`` and
``json_decoder_class``. The defaults are the library's ``ObjectJSONEncoder`` and
``ObjectJSONDecoder`` which can be extended to support types of value objects that are not
currently supported by the library.

The code below extends the JSON transcoding to support sets.


.. code:: python

    from eventsourcing.utils.transcoding import ObjectJSONEncoder, ObjectJSONDecoder


    class CustomObjectJSONEncoder(ObjectJSONEncoder):
        def default(self, obj):
            if isinstance(obj, set):
                return {'__set__': list(obj)}
            else:
                return super(CustomObjectJSONEncoder, self).default(obj)


    class CustomObjectJSONDecoder(ObjectJSONDecoder):
        @classmethod
        def from_jsonable(cls, d):
            if '__set__' in d:
                return cls._decode_set(d)
            else:
                return ObjectJSONDecoder.from_jsonable(d)

        @staticmethod
        def _decode_set(d):
            return set(d['__set__'])


    customized_sequenced_item_mapper = SequencedItemMapper(
        json_encoder_class=CustomObjectJSONEncoder,
        json_decoder_class=CustomObjectJSONDecoder
    )

    domain_event = customized_sequenced_item_mapper.from_sequenced_item(
        SequencedItem(
            sequence_id=sequence1,
            position=0,
            topic='eventsourcing.domain.model.events#DomainEvent',
            data='{"foo":{"__set__":["bar","baz"]}}',
        )
    )
    assert domain_event.foo == set(["bar", "baz"])

    sequenced_item = customized_sequenced_item_mapper.to_sequenced_item(domain_event)
    assert sequenced_item.data.startswith('{"foo":{"__set__":["ba')


Application-level encryption
----------------------------

The ``SequencedItemMapper`` can be constructed with a symmetric cipher. If
a cipher is given, then the ``state`` field of every sequenced item will be
encrypted before being sent to the database. The data retrieved from the
database will be decrypted and verified, which protects against tampering.

The library provides an AES cipher object class called ``AESCipher``. It
uses the AES cipher from the Python Cryptography Toolkit, as forked by
the actively maintained `PyCryptodome project <https://pycryptodome.readthedocs.io/>`__.

The ``AESCipher`` class uses AES in GCM mode, which is a padding-less,
authenticated encryption mode. Unlike CBC, GCM doesn't need padding so
avoids potential padding oracle attacks. GCM will be faster than EAX
on x86 architectures, especially those with AES opcodes. The other AES
modes aren't supported by this class, at the moment.

The ``AESCipher`` constructor arg ``cipher_key`` is required. The key must
be either 16, 24, or 32 random bytes (128, 192, or 256 bits). Longer keys
take more time to encrypt plaintext, but produce more secure ciphertext.

Generating and storing a secure key requires functionality beyond the scope of this library.
However, the utils package does contain a function ``encode_random_bytes()`` that may help
to generate a unicode key string, representing random bytes encoded with Base64. A companion
function ``decode_random_bytes()`` decodes the unicode key string into a sequence of bytes.


.. code:: python

    from eventsourcing.utils.cipher.aes import AESCipher
    from eventsourcing.utils.random import encode_random_bytes, decode_random_bytes

    # Unicode string representing 256 random bits encoded with Base64.
    cipher_key = encode_random_bytes(num_bytes=32)

    # Construct AES-256 cipher.
    cipher = AESCipher(cipher_key=decode_random_bytes(cipher_key))

    # Encrypt some plaintext (using nonce arguments).
    ciphertext = cipher.encrypt('plaintext')
    assert ciphertext != 'plaintext'

    # Decrypt some ciphertext.
    plaintext = cipher.decrypt(ciphertext)
    assert plaintext == 'plaintext'


The ``SequencedItemMapper`` has constructor arg ``cipher``, which can
be used to pass in a cipher object, and thereby enable encryption.

.. code:: python

    # Construct sequenced item mapper to always encrypt domain events.
    ciphered_sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=StoredEvent,
        cipher=cipher,
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


Please note, the sequence ID and position values are not encrypted, necessarily. However, by encrypting the state of
the item within the application, potentially sensitive information, for example personally identifiable information,
will be encrypted in transit to the database, at rest in the database, and in all backups and other copies.


Event store
===========

The library's ``EventStore`` provides an interface to the library's cohesive mechanism for storing events as sequences
of items, and can be used directly within an event sourced application to append and retrieve its domain events.

The ``EventStore`` is constructed with a sequenced item mapper and an
active record strategy, both are discussed in detail in the sections above.


.. code:: python

    from eventsourcing.infrastructure.eventstore import EventStore

    event_store = EventStore(
        sequenced_item_mapper=sequenced_item_mapper,
        active_record_strategy=active_record_strategy,
    )


The event store's ``append()`` method can append a domain event to its sequence. The event store uses the
``sequenced_item_mapper`` to obtain a sequenced item namedtuple from a domain events, and it uses the
``active_record_strategy`` to write a sequenced item to a database.

In the code below, a ``DomainEvent`` is appended to sequence ``aggregate1`` at position ``1``.

.. code:: python

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

    assert results[0].foo == 'bar'
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
    assert result[0].foo == 'bar'

    # Get events at and above position 1.
    result = event_store.get_domain_events(aggregate1, gte=1)
    assert len(result) == 1, result
    assert result[0].foo == 'baz'

    # Get the first event in the sequence.
    result = event_store.get_domain_events(aggregate1, limit=1)
    assert len(result) == 1, result
    assert result[0].foo == 'bar'

    # Get the last event in the sequence.
    result = event_store.get_domain_events(aggregate1, limit=1, is_ascending=False)
    assert len(result) == 1, result
    assert result[0].foo == 'baz'


Optimistic concurrency control
------------------------------

It is a feature of the event store that it isn't possible successfully to append two events at the same position in
the same sequence. This condition is coded as a ``ConcurrencyError`` since a correct program running in a
single thread wouldn't attempt to append an event that it had already successfully appended.


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


This feature depends on the behaviour of the active record strategy's ``append()`` method: the event store will
raise a ``ConcurrencyError`` if a ``SequencedItemConflict`` is raised by its active record strategy.

If a command fails due to a concurrency error, the command can be retried with the lastest state. The ``@retry``
decorator can help code retries on commands.


.. code:: python

    from eventsourcing.domain.model.decorators import retry

    errors = []

    @retry(ConcurrencyError, max_retries=5)
    def set_password():
        exc = ConcurrencyError()
        errors.append(exc)
        raise exc

    try:
        set_password()
    except ConcurrencyError:
        pass
    else:
        raise Exception("Shouldn't get here")

    assert len(errors) == 5


Event store factory
-------------------

As a convenience, the library function ``construct_sqlalchemy_eventstore()``
can be used to construct an event store that uses the SQLAlchemy classes.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy import factory

    event_store = factory.construct_sqlalchemy_eventstore(session=datastore.session)


By default, the event store is constructed with the ``StoredEvent`` sequenced item namedtuple,
and the active record class ``StoredEventRecord``. The optional args ``sequenced_item_class``
and ``active_record_class`` can be used to construct different kinds of event store.


Timestamped event store
-----------------------

The examples so far have used an integer sequenced event store, where the items are sequenced by integer version.

The example below constructs an event store for timestamp-sequenced domain events, using the library active
record class ``TimestampedSequencedItemRecord``.

.. code:: python

    from uuid import uuid4

    from eventsourcing.infrastructure.sqlalchemy.activerecords import TimestampSequencedItemRecord
    from eventsourcing.utils.times import decimaltimestamp

    # Setup database table for timestamped sequenced items.
    datastore.setup_table(TimestampSequencedItemRecord)

    # Construct event store for timestamp sequenced events.
    timestamped_event_store = factory.construct_sqlalchemy_eventstore(
        sequenced_item_class=SequencedItem,
        active_record_class=TimestampSequencedItemRecord,
        sequence_id_attr_name='originator_id',
        position_attr_name='timestamp',
        session=datastore.session,
    )

    # Construct an event.
    aggregate_id = uuid4()
    event = DomainEvent(
        originator_id=aggregate_id,
        timestamp=decimaltimestamp(),
    )

    # Store the event.
    timestamped_event_store.append(event)

    # Check the event was stored.
    events = timestamped_event_store.get_domain_events(aggregate_id)
    assert len(events) == 1
    assert events[0].originator_id == aggregate_id
    assert events[0].timestamp < decimaltimestamp()


Please note, optimistic concurrent control doesn't work to maintain entity consistency, because each
event is likely to have a unique timestamp, and so conflicts are very unlikely to arise when concurrent
operations appending to the same sequence. For this reason, although domain events can be timestamped,
it is not a very good idea to store the events of an entity or aggregate as timestamp-sequenced items.
Timestamp-sequenced items are useful for storing events that are logically independent of others, such
as messages in a log, things that do not risk causing a consistency error due to concurrent operations.


.. Todo: The library function ``construct_cassandra_eventstore()`` can be used to
.. construct an event store that uses the Apache Cassandra classes.

.. .. code:: python

..    from eventsourcing.infrastructure.cassandra import factory


..    event_store = factory.construct_cassandra_eventstore(
..    )
