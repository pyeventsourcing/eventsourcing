====================
Infrastructure layer
====================

The library's infrastructure layer provides a cohesive
mechanism for storing events as sequences of items.

The entire mechanism is encapsulated by the library's
:class:`~eventsourcing.infrastructure.eventstore.EventStore`
class. The event store uses a sequenced item mapper and a
record manager.

The sequenced item mapper converts objects such as domain
events to sequenced items, and the record manager
writes sequenced items to database records. The sequenced
item mapper and the record manager operate by
reflection off a common sequenced item type.

.. contents:: :local:


Sequenced items
===============

Sequenced item types are declared as Python named tuples.
The example below is a sequenced item type with four fields.

.. code:: python

    from collections import namedtuple

    SequencedItem = namedtuple('SequencedItem', ['sequence_id', 'position', 'topic', 'data'])

The field names are arbitrary, however a
suitable database table will have matching column names.

Whatever the names of the fields, the first field of a
sequenced item will represent the identity of a sequence
to which an item belongs. The second field will represent
the position of the item in its sequence. The third field
will represent a topic to which the item pertains. And
the fourth field will represent the state of the item.


SequencedItem
-------------

The library provides a sequenced item type called
:class:`~eventsourcing.infrastructure.sequenceditem.SequencedItem`.

.. code:: python

    from eventsourcing.infrastructure.sequenceditem import SequencedItem


Like in the example above, the library's
:class:`~eventsourcing.infrastructure.sequenceditem.SequencedItem`
has four fields. The ``sequence_id`` identifies the sequence to which
the item belongs. The ``position`` identifies the position of the item
in its sequence. The ``topic`` identifies a dimension of concern to
which the item pertains. The ``state`` holds the state of the item.

A sequenced item is just a tuple, and can be used as such. In the example
below, a sequenced item happens to be constructed with a UUID to identify
a sequence. The item has also been given an integer position value, it has a
topic that happens to correspond to a domain event class in the library. The
item's state is a JSON string in which ``foo`` is ``bar``.

.. code:: python

    from uuid import uuid4

    sequence1 = uuid4()

    state = (
        '{"foo":"bar","position":0,"sequence_id":{"UUID":"%s"}}' % sequence1.hex
    ).encode('utf8')

    sequenced_item1 = SequencedItem(
        sequence_id=sequence1,
        position=0,
        topic='eventsourcing.domain.model.events#DomainEvent',
        state=state,
    )


As expected, the attributes of the sequenced item object are
simply the values given when the object was constructed.

.. code:: python


    assert sequenced_item1.sequence_id == sequence1
    assert sequenced_item1.position == 0
    assert sequenced_item1.topic == 'eventsourcing.domain.model.events#DomainEvent'
    assert sequenced_item1.state == state, sequenced_item1.state


StoredEvent
-----------

The library also provides a sequenced item type called
:class:`~eventsourcing.infrastructure.sequenceditem.StoredEvent`.
Its attributes are ``originator_id``, ``originator_version``,
``topic``, and ``state``.

The ``originator_id`` is perhaps the ID of a domain entity that
triggered the event, and is equivalent to ``sequence_id`` above.
The ``originator_version`` could be the version of a domain entity
that triggered the event, and is equivalent to ``position`` above.
The ``topic`` identifies the class of the domain event that is
stored, and is equivalent to ``topic`` above.
The ``state`` holds the state of the domain event, and is
equivalent to ``state`` above.

.. code:: python

    from eventsourcing.infrastructure.sequenceditem import StoredEvent

    aggregate1 = uuid4()

    state = (
        '{"foo":"bar","originator_version":0,"originator_id":{"UUID":"%s"}}' % aggregate1.hex
    ).encode('utf8')

    stored_event1 = StoredEvent(
        originator_id=aggregate1,
        originator_version=0,
        topic='eventsourcing.domain.model.events#DomainEvent',
        state=state,
    )
    assert stored_event1.originator_id == aggregate1
    assert stored_event1.originator_version == 0
    assert stored_event1.topic == 'eventsourcing.domain.model.events#DomainEvent'
    assert stored_event1.state == state


Sequenced item mapper
=====================

The event store uses a sequenced item mapper to map between sequenced items
and application-level objects such as domain events.

The library provides a sequenced item mapper object class called
:class:`~eventsourcing.infrastructure.sequenceditemmapper.SequencedItemMapper`.

.. code:: python

    from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper


The :class:`~eventsourcing.infrastructure.sequenceditemmapper.SequencedItemMapper`
has a constructor arg ``sequenced_item_class``, which defaults to the library's
sequenced item named tuple :class:`~eventsourcing.infrastructure.sequenceditem.SequencedItem`.


.. code:: python

    sequenced_item_mapper = SequencedItemMapper()


The method :func:`~eventsourcing.infrastructure.sequenceditemmapper.SequencedItemMapper.event_from_item`
can be used to convert sequenced item objects to application-level objects.

.. code:: python

    domain_event = sequenced_item_mapper.event_from_item(sequenced_item1)

    assert domain_event.foo == 'bar'


The method :func:`~eventsourcing.infrastructure.sequenceditemmapper.SequencedItemMapper.item_from_event`
can be used to convert application-level objects to sequenced item named tuples.


.. code:: python

    recovered_state = sequenced_item_mapper.item_from_event(domain_event).state
    assert recovered_state == sequenced_item1.state, (recovered_state, sequenced_item1.state)


If the names of the first two fields of the sequenced item named tuple (e.g. ``sequence_id``
and ``position``) do not match the names of the attributes of the application-level object
which identify a sequence and a position (e.g. ``originator_id`` and ``originator_version``)
then the attribute names can be given to the sequenced item mapper using constructor args
``sequence_id_attr_name`` and ``position_attr_name``.

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

    assert sequenced_item_mapper.item_from_event(domain_event1).sequence_id == aggregate1


Alternatively, a sequenced item named tuple type that is different from the default
:class:`~eventsourcing.infrastructure.sequenceditem.SequencedItem` namedtuple, for
example the library's :class:`~eventsourcing.infrastructure.sequenceditem.StoredEvent`
namedtuple, can be passed with the constructor arg ``sequenced_item_class``.

.. code:: python

    sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=StoredEvent
    )

    domain_event1 = sequenced_item_mapper.event_from_item(stored_event1)

    assert domain_event1.foo == 'bar', domain_event1


Since the alternative :class:`~eventsourcing.infrastructure.sequenceditem.StoredEvent`
namedtuple can be used instead of the default
:class:`~eventsourcing.infrastructure.sequenceditem.SequencedItem` namedtuple, so it is
possible to use a custom named tuple.
Which alternative you use for your project depends on your preferences for the names
in the your domain events and your persistence model.

Please note, it is required of these application-level objects that the  "topic" generated by
:func:`~eventsourcing.utils.topic.get_topic` from the object class is resolved by
:func:`~eventsourcing.utils.topic.resolve_topic` back to the same object class.

.. code:: python

    from eventsourcing.domain.model.events import CreatedEvent
    from eventsourcing.utils.topic import get_topic, resolve_topic

    topic = get_topic(CreatedEvent)
    assert resolve_topic(topic) == CreatedEvent
    assert topic == 'eventsourcing.domain.model.events#CreatedEvent'


Substitutions
-------------

The module ``eventsourcing.utils.topic`` has a module level ``dict`` called
``substitutions`` which can be configured to substitute one topic for another.
If an entity or event is moved or renamed, then any stored events that refer
to the old position will fail to resolve, unless a mapping from the old topic
to the new topic is added to the ``substitutions`` dict.


.. code:: python

    from eventsourcing.utils.topic import substitutions


    substitutions['old_topic'] = 'new_topic'


Custom JSON transcoding
-----------------------

The :class:`~eventsourcing.infrastructure.sequenceditemmapper.SequencedItemMapper`
can be constructed with optional args ``json_encoder_class`` and ``json_decoder_class``.
The defaults are the library's
:class:`~eventsourcing.utils.transcoding.ObjectJSONEncoder` and
:class:`~eventsourcing.utils.transcoding.ObjectJSONDecoder` which
can be extended to support types of value objects that are not
currently supported by the library.

The code below shows how to extend the JSON transcoding to support sets. The library
now supports encoding and decoding sets, but the example is still demonstrative.


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
        json_decoder_class=CustomObjectJSONDecoder,
        sequenced_item_class=StoredEvent,
    )
    state = (
        '{"foo":{"__set__":["bar","baz"]},"originator_version":0,"originator_id":{"UUID":"%s"}}' % sequence1.hex
    ).encode('utf8')
    domain_event = customized_sequenced_item_mapper.event_from_item(
        StoredEvent(
            originator_id=sequence1,
            originator_version=0,
            topic='eventsourcing.domain.model.events#DomainEvent',
            state=state,
        )
    )
    assert domain_event.foo == set(["bar", "baz"])

    sequenced_item = customized_sequenced_item_mapper.item_from_event(domain_event)
    assert sequenced_item.state.startswith(b'{"foo":{"__set__":["ba')


It is also possible to extend the encoder and decoder classes by registering
encode and decode functions using function decorators. This is a more convenient
way to add support for particular types.

.. code:: python

    from eventsourcing.utils.transcoding import encoder, decoder

    @encoder.register(set)
    def encode_set(obj):
        return {"__set__": sorted(list(obj))}


    @decoder.register("__set__")
    def decode_set(d):
        return set(d["__set__"])


Application-level encryption
----------------------------

The :class:`~eventsourcing.infrastructure.sequenceditemmapper.SequencedItemMapper`
can be constructed with a symmetric cipher. If a cipher is given, then the ``state``
field of every sequenced item will be encrypted before being sent to the database.
The state retrieved from the database will be decrypted and verified, which protects
against tampering.

The library provides an AES cipher object class called :class:`~eventsourcing.utils.cipher.aes.AESCipher`.
It uses the AES cipher from the Python Cryptography Toolkit, as forked by
the actively maintained `PyCryptodome project <https://pycryptodome.readthedocs.io/>`__.

The :class:`~eventsourcing.utils.cipher.aes.AESCipher` class uses AES in GCM mode, which
is a padding-less, authenticated encryption mode. Other AES modes aren't supported by this
class, at the moment.

The :class:`~eventsourcing.utils.cipher.aes.AESCipher` constructor arg ``cipher_key`` is required.
The key must be either 16, 24, or 32 random bytes (128, 192, or 256 bits). Longer keys
take more time to encrypt plaintext, but produce more secure ciphertext.

Generating and storing a secure key requires functionality beyond the scope of this library.
However, the library contains a function
:func:`~eventsourcing.utils.random.encode_random_bytes`
that may help to generate a unicode key string, representing random bytes encoded with Base64.
A companion function
:func:`~eventsourcing.utils.random.decode_bytes` decodes the unicode key
string into a sequence of bytes.

.. code:: python

    from eventsourcing.utils.cipher.aes import AESCipher
    from eventsourcing.utils.random import encode_random_bytes, decode_bytes

    # Unicode string representing 256 random bits encoded with Base64.
    cipher_key = encode_random_bytes(num_bytes=32)

    # Construct AES-256 cipher.
    cipher = AESCipher(cipher_key=decode_bytes(cipher_key))

    # Encrypt some plaintext (using nonce arguments).
    ciphertext = cipher.encrypt(b'plaintext')
    assert ciphertext != b'plaintext'

    # Decrypt some ciphertext.
    plaintext = cipher.decrypt(ciphertext)
    assert plaintext == b'plaintext'


The :class:`~eventsourcing.infrastructure.sequenceditemmapper.SequencedItemMapper`
has constructor arg ``cipher``, which can be used to pass in a cipher object, and
thereby enable encryption.

.. code:: python

    # Construct sequenced item mapper to always encrypt domain events.
    ciphered_sequenced_item_mapper = SequencedItemMapper(
        sequenced_item_class=StoredEvent,
        cipher=cipher,
    )

    # Domain event attribute ``foo`` has value ``'bar'``.
    assert domain_event1.foo == 'bar'

    # Map the domain event to an encrypted stored event namedtuple.
    stored_event = ciphered_sequenced_item_mapper.item_from_event(domain_event1)

    # Attribute names and values of the domain event are not visible in the encrypted ``state`` field.
    assert b'foo' not in stored_event.state
    assert b'bar' not in stored_event.state

    # Recover the domain event from the encrypted state.
    domain_event = ciphered_sequenced_item_mapper.event_from_item(stored_event)

    # Domain event has decrypted attributes.
    assert domain_event.foo == 'bar'


Please note, the sequence ID and position values are not encrypted, necessarily. However,
by encrypting the state of the item within the application, potentially sensitive information,
for example personally identifiable information, will be encrypted in transit to the database,
at rest in the database, and in all backups and other copies.


Record managers
===============

The event store uses a record manager to write sequenced items to database records.

The library has an abstract base class
:class:`~eventsourcing.infrastructure.base.AbstractRecordManager`
with abstract methods
:func:`~eventsourcing.infrastructure.base.AbstractRecordManager.record_items`
and
:func:`~eventsourcing.infrastructure.base.AbstractRecordManager.get_items`,
which can be used on concrete implementations to read and write sequenced items in a database.

A record manager is constructed with a ``sequenced_item_class`` and a matching
``record_class``. The field names of a suitable record class will match the field
names of the sequenced item named tuple.


SQLAlchemy
----------

The library class
:class:`~eventsourcing.infrastructure.sqlalchemy.manager.SQLAlchemyRecordManager`
is a record manager for SQLAlchemy.

To run the example below, please install the library with the
'sqlalchemy' option.

.. code::

    $ pip install eventsourcing[sqlalchemy]


The library provides record classes for SQLAlchemy, such as
:class:`~eventsourcing.infrastructure.sqlalchemy.records.IntegerSequencedRecord` and
:class:`~eventsourcing.infrastructure.sqlalchemy.records.StoredEventRecord`.
The class :class:`~eventsourcing.infrastructure.sqlalchemy.records.IntegerSequencedRecord`
matches the default
:class:`~eventsourcing.infrastructure.sequenceditem.SequencedItem`
namedtuple. The :class:`~eventsourcing.infrastructure.sqlalchemy.records.StoredEventRecord`
class matches the alternative :class:`~eventsourcing.infrastructure.sequenceditem.StoredEvent`
namedtuple. There is also a
:class:`~eventsourcing.infrastructure.sqlalchemy.records.TimestampSequencedRecord` and a
:class:`~eventsourcing.infrastructure.sqlalchemy.records.SnapshotRecord`.

The code below uses the namedtuple :class:`~eventsourcing.infrastructure.sequenceditem.StoredEvent`
and the record class :class:`~eventsourcing.infrastructure.sqlalchemy.records.StoredEventRecord`.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.records import StoredEventRecord


Database settings can be configured using
:class:`~eventsourcing.infrastructure.sqlalchemy.datastore.SQLAlchemySettings`,
which is constructed with a ``uri`` connection
string. The code below uses an in-memory SQLite database.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings

    settings = SQLAlchemySettings(uri='sqlite:///:memory:')


To help setup a database connection and tables, the library has object class
:class:`~eventsourcing.infrastructure.sqlalchemy.datastore.SQLAlchemyDatastore`.

The :class:`~eventsourcing.infrastructure.sqlalchemy.datastore.SQLAlchemyDatastore`
is constructed with the ``settings`` object, and a tuple of record classes passed
using the ``tables`` arg.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore

    datastore = SQLAlchemyDatastore(
        settings=settings,
        tables=(StoredEventRecord,)
    )


Please note, if you have declared your own SQLAlchemy model ``Base`` class, you may wish to define your own
record classes which inherit from your ``Base`` class. If so, if may help to refer to the library record
classes to see how SQLALchemy ORM columns and indexes can be used to persist sequenced items.

The methods
:func:`~eventsourcing.infrastructure.sqlalchemy.datastore.SQLAlchemyDatastore.setup_connection`
and
:func:`~eventsourcing.infrastructure.sqlalchemy.datastore.SQLAlchemyDatastore.setup_tables`
of a datastore object can be used to setup the database connection and the tables.

.. code:: python

    datastore.setup_connection()
    datastore.setup_tables()


As well as ``sequenced_item_class`` and a matching ``record_class``, the
:class:`~eventsourcing.infrastructure.sqlalchemy.manager.SQLAlchemyRecordManager`
requires a scoped session object, passed using the constructor arg ``session``. For convenience, the
:class:`~eventsourcing.infrastructure.sqlalchemy.datastore.SQLAlchemyDatastore`
has a thread-scoped session facade set as its a ``session`` attribute. You may
wish to use a different scoped session facade, such as a request-scoped session
object provided by a Web framework.

With the database setup, an
:class:`~eventsourcing.infrastructure.sqlalchemy.manager.SQLAlchemyRecordManager`
can be constructed, and used to store events using SQLAlchemy.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.manager import SQLAlchemyRecordManager

    record_manager = SQLAlchemyRecordManager(
        sequenced_item_class=StoredEvent,
        record_class=StoredEventRecord,
        session=datastore.session,
        contiguous_record_ids=True,
        application_name=uuid4().hex
    )

Sequenced items (or "stored events" in this example) can
be appended to the database using the
:func:`~eventsourcing.infrastructure.base.AbstractRecordManager.record_items`
method of the record manager.

.. code:: python

    record_manager.record_item(stored_event1)


All the previously appended items of a sequence can be retrieved by using the
:func:`~eventsourcing.infrastructure.base.AbstractRecordManager.list_items`
method.

.. code:: python

    results = record_manager.list_items(aggregate1)


Since by now only one item was stored, so there is only one item in the results.

.. code:: python

    assert len(results) == 1
    assert results[0] == stored_event1


SQLAlchemy dialects
~~~~~~~~~~~~~~~~~~~

The databases supported by core `SQLAlchemy dialects <http://docs.sqlalchemy.org/en/latest/dialects/>`__
are Firebird, Microsoft SQL Server, MySQL, Oracle, PostgreSQL, SQLite, and Sybase. This library's
infrastructure classes for SQLAlchemy have been tested with MySQL, PostgreSQL, and SQLite.

MySQL
~~~~~

.. For MySQL, the Python package `mysqlclient <https://pypi.python.org/pypi/mysqlclient>`__
.. can be used.

For MySQL, the Python package `mysql-connector-python-rf <https://pypi.python.org/pypi/mysql-connector-python-rf>`__
can be used (licenced GPL v2). Please note, I had problems running this driver with Python 2.7 (unicode error
when it raises exceptions).

.. code::

    $ pip install pymysql-connector-python-rf

The ``uri`` for MySQL used with this driver would look something like this.

.. code::

    mysql+pymysql://username:password@localhost/eventsourcing?charset=utf8mb4&binary_prefix=true


Alternatively for MySQL, the Python package `mysqlclient <https://pypi.python.org/pypi/mysqlclient>`__
can be used (also licenced GPL v2). I didn't have problems using this driver with Python 2.7.

.. code::

    $ pip install mysqlclient

The ``uri`` for MySQL used with this driver would look something like this.

.. code::

    mysql+mysqldb://username:password@localhost/eventsourcing?charset=utf8mb4&binary_prefix=true


Another alternative is `PyMySQL <https://pypi.python.org/pypi/PyMySQL>`__. It has a BSD licence.

.. code::

    $ pip install PyMySQL

The ``uri`` for MySQL used with this driver would look something like this.

.. code::

    mysql+pymysql://username:password@localhost/eventsourcing?charset=utf8mb4&binary_prefix=true


PostgreSQL
~~~~~~~~~~

For PostgreSQL, the Python package `psycopg2 <https://pypi.python.org/pypi/psycopg2>`__
can be used.

.. code::

    $ pip install psycopg2

The ``uri`` for PostgreSQL used with this driver would look something like this.

.. code::

    postgresql+psycopg2://username:password@localhost:5432/eventsourcing


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

The library has a record manager for the Django ORM provided by
:class:`~eventsourcing.infrastructure.django.manager.DjangoRecordManager` class.

To run the example below, please install the library with the
'django' option.

.. code::

    $ pip install eventsourcing[django]


For the :class:`~eventsourcing.infrastructure.django.manager.DjangoRecordManager`, the
:class:`~eventsourcing.infrastructure.django.models.IntegerSequencedRecord`
matches the :class:`~eventsourcing.infrastructure.sequenceditem.SequencedItem`
namedtuple. The
:class:`~eventsourcing.infrastructure.django.models.StoredEventRecord` from the
same module matches the :class:`~eventsourcing.infrastructure.sequenceditem.StoredEvent`
namedtuple. There is also a
:class:`~eventsourcing.infrastructure.django.models.TimestampSequencedRecord` and a
:class:`~eventsourcing.infrastructure.django.models.SnapshotRecord`.
These are all Django models.

The package :mod:`eventsourcing.infrastructure.django` is a little Django app. To involve
its models in your Django project, simply include the application in your project's list
of ``INSTALLED_APPS``.

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


Alternatively, import or write the classes you want into one of your own Django app's ``models.py``.

The Django application at :mod:`eventsourcing.infrastructure.django` has database
migrations that will add four tables, one for each of the
record classes mentioned above. So if you use the application directly in
``INSTALLED_APPS`` then the app's migrations will be picked up by Django.

If, instead of using the app directly, you import some of its model classes
into your own application's ``models.py``, you will need to run
``python manage.py makemigrations`` before tables for event sourcing can be
created by Django. This way you can avoid creating tables you won't use.

The library has a little Django project for testing the library's Django app,
it is used in this example to help run the library's Django app.

.. code:: python

    import os

    os.environ['DJANGO_SETTINGS_MODULE'] = 'eventsourcing.tests.djangoproject.djangoproject.settings'


This Django project is simply the files that ``django-admin.py startproject`` generates, with the SQLite
database set to be in memory, and with the library's Django app added to the ``INSTALLED_APPS`` setting.

With the environment variable ``DJANGO_SETTINGS_MODULE`` referring to the Django project, Django can be
started. If you aren't running tests with the Django test runner, you may need to run ``django.setup()``.

.. code:: python

    import django

    django.setup()


Before using the database, make sure the migrations have been applied, so the necessary database tables exist.

An alternative to ``python manage.py migrate`` is the ``call_command()``
function, provided by Django. If you aren't running tests with the Django
test runner, this can help e.g. to setup an SQLite database in memory
before each test by calling it in the ``setUp()`` method of a test case.

.. code:: python

    from django.core.management import call_command

    call_command('migrate', verbosity=0, interactive=False)


So long as a table exists for its record class, the
:class:`~eventsourcing.infrastructure.django.manager.DjangoRecordManager`
can be used to store events using the Django ORM.

.. code:: python

    from eventsourcing.infrastructure.django.manager import DjangoRecordManager
    from eventsourcing.infrastructure.django.models import StoredEventRecord

    django_record_manager = DjangoRecordManager(
        record_class=StoredEventRecord,
        sequenced_item_class=StoredEvent,
        contiguous_record_ids=True,
        application_name='demo',
    )

    results = django_record_manager.list_items(aggregate1)
    assert len(results) == 0

    django_record_manager.record_item(stored_event1)

    results = django_record_manager.list_items(aggregate1)
    assert results[0] == stored_event1


Django backends
~~~~~~~~~~~~~~~

The supported `Django backends <https://docs.djangoproject.com/en/2.0/ref/databases/>`__
are PostgreSQL, MySQL, SQLite, and Oracle. This library's Django infrastructure classes
have been tested with PostgreSQL, MySQL, SQLite.


Contiguous record IDs
---------------------

The ``contiguous_record_ids`` argument, used in the examples above, is
optional, and is by default ``False``. If set to a ``True`` value, and
if the record class has an ID field, then the records will be inserted
(using an "insert select from" query) that generates a table of records
with IDs that form a contiguous integer sequence.

Application events recorded in this way can be accurately followed as
a single sequence without overbearing complexity to mitigate gaps and
race conditions. This feature is only available on the relational
record managers (Django and SQLAlchemy, not Cassandra).

If the record ID is merely auto-incrementing, as it is when the
the library's integer sequenced record classes are used without
this feature being enabled, then gaps could be generated. Whenever
there is contention in the aggregate sequence (record ID) that
causes the unique record ID constraint to be violated, the
transaction will being rolled back, and an ID that was issued was
could be discarded and lost. Other greater IDs may already have
been issued. The complexity for followers is that a gap may be
permanent or temporary. It may be that a gap is eventually filled
by a transaction that was somehow delayed. Although some database
appear to have auto-incrementing functionality that does not
lead to gaps even with transactions being rolled back, I don't
understand when this happens and when it doesn't and so feel
unable to reply on it, at least at the moment. It appears to be an
inherently unreliable situation that could probably be mitigated
satisfactorily by followers if they need to project the application
events accurately, but only with increased complexity.

Each relational record manager has a raw SQL query with an
"insert select from" statement. If possible, the raw query is compiled
when the record manager object is constructed. When a record is
inserted, the new field values are bound to the raw query and executed
within a transaction. When executed, the query firstly selects the
maximum ID from all records currently existing in the table (as visible
in its transaction), and then attempts to insert a record with an ID
value of the max existing ID plus one (the next unused ID). The record
table must have a unique constraint for the ID, so that records aren't
overwritten by this query. The record ID must also be indexed, so that
the max value can be identified efficiently. The b-tree commonly used
for databases indexes supports this purpose well. The transaction
isolation level must be at least "read committed", which is true by
default for MySQL and PostgreSQL.

Any resulting contention in the record ID will raise an exception so that the
query can be retried. The library exception class :class:`~eventsourcing.exceptions.RecordConflictError`
will be raised.


Cassandra
---------

The library has a record manager for
`Apache Cassandra <http://cassandra.apache.org/>`__
provided by the library class
:class:`~eventsourcing.infrastructure.cassandra.manager.CassandraRecordManager`.

.. code:: python

    from eventsourcing.infrastructure.cassandra.manager import CassandraRecordManager

To run the example below, please install the library with the
'cassandra' option.

.. code::

    $ pip install eventsourcing[cassandra]

It takes a while to build the driver. If you want to do that last step
quickly, set the environment variable ``CASS_DRIVER_NO_CYTHON``.

.. code::

    $ CASS_DRIVER_NO_CYTHON=1 pip install eventsourcing[cassandra]


For the :class:`~eventsourcing.infrastructure.cassandra.manager.CassandraRecordManager`,
the :class:`~eventsourcing.infrastructure.cassandra.records.IntegerSequencedRecord`
from :mod:`eventsourcing.infrastructure.cassandra.records` matches the
:class:`~eventsourcing.infrastructure.sequenceditem.SequencedItem`
namedtuple. The :class:`~eventsourcing.infrastructure.cassandra.records.StoredEventRecord`
from the same module matches the :class:`~eventsourcing.infrastructure.sequenceditem.StoredEvent`
namedtuple.  There is also a
:class:`~eventsourcing.infrastructure.cassandra.records.TimestampSequencedRecord`,
a :class:`~eventsourcing.infrastructure.cassandra.records.TimeuuidSequencedRecord`,
and a :class:`~eventsourcing.infrastructure.cassandra.records.SnapshotRecord`.

The :class:`~eventsourcing.infrastructure.cassandra.datastore.CassandraDatastore` and
:class:`~eventsourcing.infrastructure.cassandra.datastore.CassandraSettings` can be used
in the same was as ``SQLAlchemyDatastore`` and ``SQLAlchemySettings`` above. Please investigate
library class :class:`~eventsourcing.infrastructure.cassandra.datastore.CassandraSettings`
for information about configuring away from default settings.

.. code:: python

    from eventsourcing.infrastructure.cassandra.datastore import CassandraDatastore, CassandraSettings
    from eventsourcing.infrastructure.cassandra.records import StoredEventRecord

    cassandra_datastore = CassandraDatastore(
        settings=CassandraSettings(),
        tables=(StoredEventRecord,)
    )
    cassandra_datastore.setup_connection()
    cassandra_datastore.setup_tables()


With the database setup, the
:class:`~eventsourcing.infrastructure.cassandra.manager.CassandraRecordManager`
can be constructed, and used to store events using Apache Cassandra.

.. code:: python

    from eventsourcing.infrastructure.cassandra.manager import CassandraRecordManager

    cassandra_record_manager = CassandraRecordManager(
        record_class=StoredEventRecord,
        sequenced_item_class=StoredEvent,
    )

    results = cassandra_record_manager.list_items(aggregate1)
    assert len(results) == 0

    cassandra_record_manager.record_item(stored_event1)

    results = cassandra_record_manager.list_items(aggregate1)
    assert results[0] == stored_event1

    cassandra_datastore.drop_tables()
    cassandra_datastore.close_connection()


Sequenced item conflicts
------------------------

It is a common feature of the record manager classes that it isn't possible successfully
to append two items at the same position in the same sequence. If such an attempt is made, a
:class:`~eventsourcing.exceptions.RecordConflictError` will be raised.

.. code:: python

    from eventsourcing.exceptions import RecordConflictError

    # Fail to append an item at the same position in the same sequence as a previous item.
    try:
        record_manager.record_item(stored_event1)
    except RecordConflictError:
        pass
    else:
        raise Exception("RecordConflictError not raised")


This feature is implemented using optimistic concurrency control features of the underlying database. With
SQLAlchemy, a unique constraint is used that involves both the sequence and the position columns.
The Django ORM strategy works in the same way.

With Cassandra the position is the primary key in the sequence partition, and the "IF NOT
EXISTS" feature is applied. The Cassandra database management system implements the Paxos
protocol, and can thereby accomplish linearly-scalable distributed optimistic concurrency
control, guaranteeing sequential consistency of the events of an entity despite the database
being distributed. It is also possible to serialize calls to the methods of an entity, but
that is out of the scope of this package — if you wish to do that, perhaps something like
an actor framework or `Zookeeper <https://zookeeper.apache.org/>`__ might help.


Event store
===========

The library's :class:`~eventsourcing.infrastructure.eventstore.EventStore`
provides an interface to the library's cohesive mechanism for storing events
as sequences of items, and can be used directly within an event sourced
application to append and retrieve its domain events.

The :class:`~eventsourcing.infrastructure.eventstore.EventStore`
is constructed with a sequenced item mapper and a record
manager, both are discussed in detail in the sections above.


.. code:: python

    from eventsourcing.infrastructure.eventstore import EventStore

    event_store = EventStore(
        event_mapper=sequenced_item_mapper,
        record_manager=record_manager,
    )


The method :func:`~eventsourcing.infrastructure.eventstore.EventStore.store_events` can
store a domain event in its sequence. The event store uses its ``sequenced_item_mapper``
to obtain sequenced items (named tuple) from domain events, and it uses its
``record_manager`` to record sequenced items in the database.

In the code below, a :class:`~eventsourcing.domain.model.events.DomainEvent` is
appended to sequence ``aggregate1`` at position ``1``.

.. code:: python

    event_store.store_events([
        DomainEvent(
            originator_id=aggregate1,
            originator_version=1,
            foo='baz',
        )
    ])


The method :func:`~eventsourcing.infrastructure.base.AbstractEventStore.list_events` can
be used to get events that have previously been stored. The event store uses its
``record_manager`` to get the sequenced items from database records, and it uses
its ``sequenced_item_mapper`` to obtain domain events from the sequenced items.

.. code:: python

    results = event_store.list_events(aggregate1)


Since by now two domain events have been stored, so there are two domain events in the results.


.. code:: python

    assert len(results) == 2

    assert results[0].foo == 'bar'
    assert results[1].foo == 'baz'


The optional arguments of
:func:`~eventsourcing.infrastructure.base.AbstractEventStore.list_events`
can be used to select some of the items in the sequence.

The ``lt`` arg is used to select items below the given position in the sequence.

The ``lte`` arg is used to select items below and at the given position in the sequence.

The ``gte`` arg is used to select items at and above the given position in the sequence.

The ``gt`` arg is used to select items above the given position in the sequence.

The ``limit`` arg is used to limit the number of items selected from the sequence.

The ``is_ascending`` arg is used when selecting items. It affects how any ``limit`` is applied, and determines the
order of the results. Hence, it can affect both the content of the results and the performance of the method.


.. code:: python

    # Get events below and at position 0.
    result = event_store.list_events(aggregate1, lte=0)
    assert len(result) == 1, result
    assert result[0].foo == 'bar'

    # Get events at and above position 1.
    result = event_store.list_events(aggregate1, gte=1)
    assert len(result) == 1, result
    assert result[0].foo == 'baz'

    # Get the first event in the sequence.
    result = event_store.list_events(aggregate1, limit=1)
    assert len(result) == 1, result
    assert result[0].foo == 'bar'

    # Get the last event in the sequence.
    result = event_store.list_events(aggregate1, limit=1, is_ascending=False)
    assert len(result) == 1, result
    assert result[0].foo == 'baz'


Optimistic concurrency control
------------------------------

It is a feature of the event store that it isn't possible successfully
to append two events at the same position in the same sequence. This condition
is coded as a :class:`~eventsourcing.exceptions.ConcurrencyError` since
a correct program running in a single thread wouldn't attempt to append
an event that it had already successfully appended. The exception class
:class:`~eventsourcing.exceptions.ConcurrencyError` is a subclass of the
exception class :class:`~eventsourcing.exceptions.RecordConflictError`.

.. code:: python

    from eventsourcing.exceptions import ConcurrencyError

    # Fail to append an event at the same position in the same sequence as a previous event.
    try:
        event_store.store_events([
            DomainEvent(
                originator_id=aggregate1,
                originator_version=1,
                foo='baz',
            )
        ])
    except ConcurrencyError:
        pass
    else:
        raise Exception("ConcurrencyError not raised")


This feature depends on the behaviour of the record manager method
:class:`~eventsourcing.infrastructure.base.AbstractRecordManager.record_items`.
The event store will raise a
:class:`~eventsourcing.exceptions.ConcurrencyError` if a
:class:`~eventsourcing.exceptions.RecordConflictError`
is raised by its record manager.

If a command fails due to a concurrency error, the command can be
retried with the latest state. The decorator
:func:`~eventsourcing.domain.model.decorators.retry`
can help code retries on commands.

.. code:: python

    from eventsourcing.domain.model.decorators import retry

    errors = []

    @retry(ConcurrencyError, max_attempts=5)
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

This feature avoids the sequence of records being corrupted due to concurrent threads
operating on the same aggregate. However, the result is that success of appending an event in
such circumstances is only probabilistic with respect to concurrency conflicts. Concurrency
conflicts can be avoided if all commands for a single aggregate are executed in series, for
example by treating each aggregate as an actor within an actor framework, or with locks provided
by something like Zookeeper.


Infrastructure factory
======================

To help with construction of infrastructure objects, the library
has a various infrastructure factory classes. The abstract base class
:class:`~eventsourcing.infrastructure.factory.InfrastructureFactory`
defines the common method signatures. The concrete subclass
:class:`~eventsourcing.infrastructure.sqlalchemy.factory.SQLAlchemyInfrastructureFactory`
helps with construction of SQLAlchemy infrastructure. Similarly
:class:`~eventsourcing.infrastructure.django.factory.DjangoInfrastructureFactory`
helps with Django infrastructure and
:class:`~eventsourcing.infrastructure.cassandra.factory.CassandraInfrastructureFactory`
helps with Cassandra.

.. .. code:: python
..
..     from eventsourcing.infrastructure.sqlalchemy import factory
..
..     event_store = factory.construct_sqlalchemy_eventstore(
..         session=datastore.session,
..         application_name=uuid4().hex,
..         contiguous_record_ids=True,
..     )
..
..
.. By default, the event store is constructed with the
.. :class:`~eventsourcing.infrastructure.sequenceditem.StoredEvent` sequenced item named tuple,
.. and the record class ``StoredEventRecord``. The optional args ``sequenced_item_class``
.. and ``record_class`` can be used to construct different kinds of event store.
..
..
.. Timestamped event store
.. -----------------------
..
.. The examples so far have used an integer sequenced event store, where the items are sequenced by integer version.
..
.. The example below constructs an event store for timestamp-sequenced domain events, using the library
.. record class ``TimestampSequencedRecord``.
..
.. .. code:: python
..
..     from uuid import uuid4
..
..     from eventsourcing.infrastructure.sqlalchemy.records import TimestampSequencedRecord
..     from eventsourcing.utils.times import decimaltimestamp
..
..     # Setup database table for timestamped sequenced items.
..     datastore.setup_table(TimestampSequencedRecord)
..
..     # Construct event store for timestamp sequenced events.
..     timestamped_event_store = factory.construct_sqlalchemy_eventstore(
..         sequenced_item_class=SequencedItem,
..         record_class=TimestampSequencedRecord,
..         sequence_id_attr_name='originator_id',
..         position_attr_name='timestamp',
..         session=datastore.session,
..     )
..
..     # Construct an event.
..     aggregate_id = uuid4()
..     event = DomainEvent(
..         originator_id=aggregate_id,
..         timestamp=decimaltimestamp(),
..     )
..
..     # Store the event.
..     timestamped_event_store.store_events([event])
..
..     # Check the event was stored.
..     events = timestamped_event_store.list_events(aggregate_id)
..     assert len(events) == 1
..     assert events[0].originator_id == aggregate_id
..     assert events[0].timestamp < decimaltimestamp()
..
..
.. Please note, optimistic concurrent control doesn't work with timestamped sequenced items to maintain
.. consistency of a domain entity, because each event is likely to have a unique timestamp, and so
.. branches can occur without restraint. Optimistic concurrency control will prevent one timestamp
.. sequenced event from overwritting another. For this reason, although domain events are usefully timestamped,
.. it is not a very good idea to store the events of an entity or aggregate as timestamp-sequenced items.
.. Timestamp-sequenced items are useful for storing events that are logically independent of others, such
.. as messages in a log, things that do not risk causing a consistency error due to concurrent operations.
.. It remains that timestamp sequenced items can happen to occur at the same timestamp, in which case
.. there would be a concurrency error exception, and the event could be retried with a later timestamp.
..
..
.. TimeUUIDs
.. ~~~~~~~~~
..
.. If throughput is so high that such conflicts are too frequent, the library also supports sequencing
.. items by TimeUUID, which includes a random component that makes it very unlikely two events will
.. conflict. This feature currently works with Apache Cassandra only. Tests exist in the library, other
.. documentation is forthcoming.
..
