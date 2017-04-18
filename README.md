# Event Sourcing in Python

[![Build Status](https://secure.travis-ci.org/johnbywater/eventsourcing.png?branch=master)](https://travis-ci.org/johnbywater/eventsourcing)
[![Coverage Status](https://coveralls.io/repos/github/johnbywater/eventsourcing/badge.svg?branch=master#123)](https://coveralls.io/github/johnbywater/eventsourcing?branch=master)
[![Gitter chat](https://badges.gitter.im/gitterHQ/services.png)](https://gitter.im/eventsourcing-in-python/eventsourcing)

A library for event sourcing in Python.


## Install

Use pip to install the [latest distribution](https://pypi.python.org/pypi/eventsourcing) from
the Python Package Index.

    pip install eventsourcing

If you want to use SQLAlchemy, then please install with 'sqlalchemy'.

    pip install eventsourcing[sqlalchemy]

Similarly, if you want to use Cassandra, then please install with 'cassandra'.

    pip install eventsourcing[cassandra]

If you want to run the test suite, then please install with the 'test' optional extra.

    pip install eventsourcing[test]

After installing with 'test', and installing Cassandra locally, the test suite should pass.

    python -m unittest discover eventsourcing.tests -v

Please register any [issues on GitHub](https://github.com/johnbywater/eventsourcing/issues).

There is also a [mailing list](https://groups.google.com/forum/#!forum/eventsourcing-users).
And a [room on Gitter](https://gitter.im/eventsourcing-in-python/eventsourcing)


## Overview

What is event sourcing? One definition suggests the state of an event sourced application
is determined by a sequence of events. Another definition has event sourcing as a
persistence mechanism for domain driven design. In any case, it is common for the state
of a software application to be distributed or partitioned across a set of entities or aggregates
in a domain model.

Therefore, this library provides mechanisms useful in event sourced applications: a style
for coding entity behaviours that emit events; and a way for the events of an
entity to be stored and replayed to obtain the entities on demand.

This document provides instructions for installing the package, highlights the main features of
the library, includes a detailed example of usage, describes the design of the software, and has
some background information about the project.

## Features

**Event store** — appends and retrieves domain events. The event store uses a
"sequenced item mapper" and an "active record strategy" to map domain events
to a database in ways that can be easily substituted.

**Persistence policy** — subscribes to receive published domain events.
Appends received domain events to an event store whenever a domain event is
published. Domain events are typically published by the methods of an entity.

**Event player** — reconstitutes entities by replaying events, optionally with
snapshotting. An event player is used by an entity repository to determine the
state of an entity. The event player retrieves domain events from the event store. 

**Sequenced item mapper** — maps between domain events and "sequenced items", the archetype
persistence model used by the library to store domain events. The library supports two
different kinds of sequenced item: items that are sequenced by an increasing series
of integers; and items that are sequenced in time. They support two different kinds of
domain events: events of versioned entities (e.g. an aggregate in domain driven design),
and unversioned timestamped events (e.g. entries in a log).

**Active record strategy** — maps between "sequenced items" and database records (ORM).
Support can be added for a new database schema by introducing a new active record strategy.

**Snapshotting** — avoids replaying an entire event stream to
 obtain the state of an entity. A snapshot strategy is included which reuses
the capabilities of this library by implementing snapshots as time-sequenced domain
events. It can easily be substituted with one that uses a dedicated table for snapshots.

**Application-level encryption** — encrypts and decrypts stored events, using a cipher
strategy passed as an option to the sequenced item mapper. Can be used to encrypt some
events, or all events, or not applied at all (the default). Included is a cipher strategy
which uses a standard AES cipher, by default in CBC mode with 128 bit blocksize and a 16
byte encryption key, and which generates a unique 16 byte initialization vector for each
encryption. In this cipher strategy, data is compressed before it is encrypted, which can
mean application performance is improved when encryption is enabled.

**Optimistic concurrency control** — can be used to ensure a distributed or
horizontally scaled application doesn't become inconsistent due to concurrent
method execution. Leverages any optimistic concurrency controls in the database
adapted by the stored event repository. For example the Cassandra database, which implements
the Paxos protocol, can accomplish linearly-scalable distributed optimistic concurrency
control, guaranteeing sequential consistency of the events of an entity, across concurent
application threads. It is also possible to serialize calls to the methods of an
entity, but that is out of the scope of this package — if you wish to do that,
perhaps something like [Zookeeper](https://zookeeper.apache.org/) might help.

**Abstract base classes** — suggest how to structure an event sourced application.
The library has base classes for application objects, domain entities, entity repositories,
domain events of various types, mapping strategies, snapshotting strategies, cipher strategies,
test cases, etc. They are well factored, relatively simple, and can be easily extended for your own
purposes. If you wanted to create a domain model that is entirely stand-alone (recommended by
purists for maximum longevity), you might start by copying the library classes.

**Synchronous publish-subscribe mechanism** — propagates events from publishers to subscribers.
Stable and deterministic, with handlers called in the order they are registered, and with which
calls to publish events do not return until all event subscribers have returned. In general,
subscribers are policies of the application, which may execute further commands whenever a
particular kind of event is received. Publishers of domain events are typically methods of domain entities.

**Worked examples** — a simple worked example application (see below) with an example
entity class, with example domain events, an example factory method, an example mutator function,
and an example database table.


## Usage

This section describes how to write an event sourced application.

This example follows the layered architecture: application, domain, and infrastructure.

To create a working program, you can copy and paste the following code snippets into
a single Python file. The code snippets in this section have been tested. Please feel
free to experiment by making variations. 

If you are using a Python virtualenv, please check that your virtualenv is activated
before installing the library and running your program.

Install the library with the 'sqlalchemy' and 'crypto' options.

    pip install eventsourcing[sqlalchemy,crypto]


### Step 1: Domain model

Let's start with the domain model. Because the state of an event sourced application
is determined by a sequence of events, we need to define some events.

#### Domain events

For the sake of simplicity in this example, let's assume things in our 
domain can be "created", "changed", and "discarded". With that in mind,
let's define some domain event classes.

In the example below, the common attributes of a domain event, such as the entity ID
and version, and the timestamp of the event, have been pulled up to a layer supertype
called ```DomainEvent```.

```python
import time

class DomainEvent(object):
    """Layer supertype."""

    def __init__(self, entity_id, entity_version, timestamp=None, **kwargs):
        self.entity_id = entity_id
        self.entity_version = entity_version
        self.timestamp = timestamp or time.time()
        self.__dict__.update(kwargs)


class Created(DomainEvent):
    """Published when an entity is created."""
    def __init__(self, **kwargs):
        super(Created, self).__init__(entity_version=0, **kwargs)

    
class ValueChanged(DomainEvent):
    """Published when an attribute value is changed."""
    def __init__(self, name, value, **kwargs):
        super(ValueChanged, self).__init__(**kwargs)
        self.name = name
        self.value = value


class Discarded(DomainEvent):
    """Published when an entity is discarded."""
```

Please note, the domain event classes above do not depend on the library. The library does
however contain a collection of different kinds of domain event classes that you can use
in your models, for example see ```AggregateEvent```. The domain event classes in the
library are slightly more sophisticated than the code in this example.


#### Domain entity

Now, let's use the event classes above to define an "example" entity.

The ```Example``` entity class below has an entity ID, a version number, and a
timestamp. It also has a property ```foo```, and a ```discard()``` method to use
when the entity is discarded. The factory method ```create_new_example()``` can
be used to create new entities.

All the methods follow a similar pattern. Each constructs an event that represents the result
of the operation. Each uses a "mutator function" function ```mutate()``` to apply the event
to the entity. Then each publishes the event for the benefit of any subscribers.

When replaying a sequence of events, for example when reconsistuting an entity from its
domain events, the mutator function is also successively to apply every event to an evolving
initial state. For the sake of simplicity in this example, we'll use an if-else block
that can handle the three types of events defined above.

```python
import uuid

from eventsourcing.domain.model.events import publish


class Example(object):
    """Example domain entity."""
    def __init__(self, entity_id, entity_version=0, foo='', timestamp=None):
        self._id = entity_id
        self._version = entity_version
        self._is_discarded = False
        self._created_on = timestamp
        self._last_modified_on = timestamp
        self._foo = foo

    @property
    def id(self):
        return self._id

    @property
    def version(self):
        return self._version

    @property
    def is_discarded(self):
        return self._is_discarded

    @property
    def created_on(self):
        return self._created_on

    @property
    def last_modified_on(self):
        return self._last_modified_on

    @property
    def foo(self):
        return self._foo
    
    @foo.setter
    def foo(self, value):
        assert not self._is_discarded    
        # Instantiate a domain event.
        event = ValueChanged(
            entity_id=self.id,
            entity_version=self.version,
            name='foo',
            value=value,
        )
        # Apply the event to self.
        mutate(self, event)
        # Publish the event for others.
        publish(event)

    def discard(self):
        assert not self._is_discarded
        # Instantiate a domain event.
        event = Discarded(entity_id=self.id, entity_version=self.version)
        # Apply the event to self.
        mutate(self, event)
        # Publish the event for others.
        publish(event)


def create_new_example(foo):
    """Factory method for Example entities."""
    # Create an entity ID.
    entity_id = uuid.uuid4()
    # Instantiate a domain event.
    event = Created(entity_id=entity_id, foo=foo)
    # Mutate the event to construct the entity.
    entity = mutate(None, event)
    # Publish the event for others.
    publish(event=event)
    # Return the new entity.
    return entity


def mutate(entity, event):
    """Mutator function for Example entities."""
    # Handle "created" events by instantiating the entity class.
    if isinstance(event, Created):
        entity = Example(**event.__dict__)
        entity._version += 1
        return entity
    # Handle "value changed" events by setting the named value.
    elif isinstance(event, ValueChanged):
        assert not entity.is_discarded
        setattr(entity, '_' + event.name, event.value)
        entity._version += 1
        entity._last_modified_on = event.timestamp
        return entity
    # Handle "discarded" events by returning 'None'.
    elif isinstance(event, Discarded):
        assert not entity.is_discarded
        entity._version += 1
        entity._is_discarded = True
        return None
    else:
        raise NotImplementedError(type(event))
```

Apart from using the library's ```publish()``` function, the example entity class does not depend on the
library. It doesn't inherit from a "magical" entity base class. It just publishes events that it has
applied to itself. The library does however contain domain entity classes that you can use to build your
domain model. For example see the ```TimestampedVersionedEntity``` class, which is also a timestamped,
versioned entity. The library classes are slightly more refined than the code in this example.


#### Run the code

With this stand-alone code, we can create a new example entity object. We can update its property
```foo```, and we can discard the entity using the ```discard()``` method. Let's firstly subscribe to
receive the events that will be published, so we can see what happened.

```python
from eventsourcing.domain.model.events import subscribe

# A list of received events.
received_events = []

# Subscribe to receive published events.
subscribe(lambda e: received_events.append(e))

# Create a new entity using the factory.
entity = create_new_example(foo='bar1')

# Check the entity has an ID.
assert entity.id

# Check the entity has a version number.
assert entity.version == 1

# Check the received events.
assert len(received_events) == 1, received_events
assert isinstance(received_events[0], Created)
assert received_events[0].entity_id == entity.id
assert received_events[0].entity_version == 0
assert received_events[0].foo == 'bar1'

# Check the value of property 'foo'.
assert entity.foo == 'bar1'

# Update property 'foo'.
entity.foo = 'bar2'

# Check the new value of 'foo'.
assert entity.foo == 'bar2'

# Check the version number has increased.
assert entity.version == 2

# Check the received events.
assert len(received_events) == 2, received_events
assert isinstance(received_events[1], ValueChanged)
assert received_events[1].entity_version == 1
assert received_events[1].name == 'foo'
assert received_events[1].value == 'bar2'
```


### Step 2: Infrastructure

Since the application state is determined by a sequence of events, the events of the
application must somehow be stored, and the entities somehow retrieved.

#### Database table

Let's start by setting up a simple database. We can use SQLAlchemy to define a
database table that stores integer-sequenced items.

```python
from sqlalchemy.ext.declarative.api import declarative_base
from sqlalchemy.sql.schema import Column, Sequence, UniqueConstraint
from sqlalchemy.sql.sqltypes import BigInteger, Integer, String, Text
from sqlalchemy_utils import UUIDType

Base = declarative_base()


class SequencedItemTable(Base):
    __tablename__ = 'sequenced_items'

    id = Column(Integer(), Sequence('integer_sequened_item_id_seq'), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(UUIDType(), index=True)

    # Position (index) of item in sequence.
    position = Column(BigInteger(), index=True)

    # Topic of the item (e.g. path to domain event class).
    topic = Column(String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = Column(Text())

    # Unique constraint.
    __table_args__ = UniqueConstraint('sequence_id', 'position',
                                      name='integer_sequenced_item_uc'),
```

Now create the database table. The SQLAlchemy objects can be adapted with a ```Datastore``` from the 
library, which provides a common interface for the operations ```setup_connection()```
and ```setup_tables()```.

```python
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings, SQLAlchemyDatastore

datastore = SQLAlchemyDatastore(
    base=Base,
    settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
    tables=(SequencedItemTable,),
)

datastore.setup_connection()
datastore.setup_tables()
```

This example uses an SQLite in memory relational database. You can
change ```uri``` to any valid connection string. Here are some example
connection strings: for an SQLite file; for a PostgreSQL database; and
for a MySQL database. See SQLAlchemy's create_engine() documentation for details.

```
sqlite:////tmp/mydatabase

postgresql://scott:tiger@localhost:5432/mydatabase

mysql://scott:tiger@hostname/dbname
```


#### Event store

To support different kinds of sequences, and to allow for different schemas
for storing events, the event store has been factored to use a "sequenced
item mapper" to map domain events to sequenced items, and an "active record
strategy" to write sequenced items into a database table. The details
have been made explicit so they can be easily replaced.

The sequenced item mapper derives the values of sequenced item fields from
the attributes of domain events. The active record strategy uses an active
record class to access rows in a database table. Hence you you could vary the
field types and indexes used in the database table by passing in an alternative
active record class. You can use alternative field names in the database
table by using an alternative sequenced item class, along with a suitable active
record class, reusing the sequenced item mapper and the active record strategy.

You can extend or replace the persistence model by extending the sequenced item
mapper and sequenced item class, and using them along with a suitable active
record class. A new database system or service can be adapted with a new active
record strategy.

In the code below, the args ```sequence_id_attr_name``` and ```position_attr_name```
inform the sequenced item mapper which domain event attributes should be used for the
sequence ID and position fields of a sequenced item. It isn't necessary to
provide the ```sequence_id_attr_name``` arg, if the name of the domain event
attribute holding the sequence ID value is equal to the name of the first field
of the sequenced item class - for example if both are called 'aggregate_id'. Similarly,
it isn't necessary to provide a value for the ```position_attr_name``` arg, if the name
of the domain event attribute which indicates the position of the event in a sequence
is equal to the name of the second field of the sequence item class - for example if both
are called 'aggregate_version' (see below).


```python
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
from eventsourcing.infrastructure.sequenceditem import SequencedItem
from eventsourcing.infrastructure.sequenceditemmapper import SequencedItemMapper

active_record_strategy = SQLAlchemyActiveRecordStrategy(
    datastore=datastore,
    active_record_class=SequencedItemTable,
    sequenced_item_class=SequencedItem
)

sequenced_item_mapper = SequencedItemMapper(
    sequenced_item_class=SequencedItem,
    sequence_id_attr_name='entity_id',
    position_attr_name='entity_version'
)

event_store = EventStore(
    active_record_strategy=active_record_strategy,
    sequenced_item_mapper=sequenced_item_mapper
)
```

#### Entity repository

It is common pattern to retrieve entities from a repository. An event sourced
repository for the ```example``` entity class can be constructed directly using the
```EventSourcedRepository``` library class. The repository is given the mutator function
```mutate()``` and the event store, so that it can make an event player.


```python
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository

example_repository = EventSourcedRepository(
    event_store=event_store,
    mutator=mutate
)
```

#### Run the code

Now, let's firstly write the events we received earlier into the event store.

```python

# Put each received event into the event store.
for event in received_events:
    event_store.append(event)

# Check the events exist in the event store.
stored_events = event_store.get_domain_events(entity.id)
assert len(stored_events) == 2, (received_events, stored_events)
```

The entity can now be retrieved from the repository, using its dictionary-like interface.

```python
retrieved_entity = example_repository[entity.id]
assert retrieved_entity.foo == 'bar2'
```

Remember that we can always get the sequenced items directly from the active record
strategy. A sequenced item is tuple containing a serialised representation of the domain event. In the library, a
```SequencedItem``` is a Python tuple with four fields: ```sequence_id```, ```position```,
```topic```, and ```data```. By default, an event's ```entity_id``` attribute is mapped to the ```sequence_id``` field,
and the event's ```entity_version``` attribute is mapped to the ```position``` field. The ```topic``` field of a
sequenced item is used to identify the event class, and the ```data``` field represents the state of the event (a 
JSON string).

```python
sequenced_items = event_store.active_record_strategy.get_items(entity.id)

assert len(sequenced_items) == 2

assert sequenced_items[0].sequence_id == entity.id
assert sequenced_items[0].position == 0
assert 'Created' in sequenced_items[0].topic
assert 'bar1' in sequenced_items[0].data

assert sequenced_items[1].sequence_id == entity.id
assert sequenced_items[1].position == 1
assert 'ValueChanged' in sequenced_items[1].topic
assert 'bar2' in sequenced_items[1].data
```

Similar to the support for storing events in SQLAlchemy, there
are classes in the library for Cassandra. Support for other
databases is forthcoming.


### Step 3: Application

Although we can do everything at the module level, an application object brings
everything together. In the example below, the application has an event store,
and an entity repository.

Most importantly, the application has a persistence policy. The persistence
policy firstly subscribes to receive events when they are published, and it
uses the event store to store all the events that it receives.

As a convenience, it is useful to make the application function as a Python
context manager, so that the application can close the persistence policy,
unsubscribing itself from receiving further domain events.

```python
from eventsourcing.application.policies import PersistencePolicy

class Application(object):

    def __init__(self, datastore):
        self.event_store = EventStore(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                datastore=datastore,
                active_record_class=SequencedItemTable,
                sequenced_item_class=SequencedItem,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name='entity_id',
                position_attr_name='entity_version',
            )
        )
        self.example_repository = EventSourcedRepository(
            event_store=self.event_store,
            mutator=mutate,
        )
        self.persistence_policy = PersistencePolicy(self.event_store, event_type=DomainEvent)
        
    def create_example(self, foo):
        return create_new_example(foo=foo)
        
    def close(self):
        self.persistence_policy.close()

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
```

After instantiating the application, we can create more example entities
and expect they will be available in the repository immediately.

Please note, a discarded entity can not be retrieved from the repository.
The repository's dictionary-like interface will raise a Python ```KeyError```
exception instead of returning an entity.

```python
with Application(datastore) as app:

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
```

Congratulations. You have created yourself an event sourced application.

A slightly more developed example application can be found in the library
module ```eventsourcing.example.application```.


### Step 4: Snapshotting

To enable snapshotting, pass in a snapshotting strategy object when constructing
an entity repository.

The snapshotting strategy object depends on infrastructure. There are several
options, but here we will simply use a separate table for snapshots.

```python
class SnapshotTable(Base):
    __tablename__ = 'snapshots'

    id = Column(Integer(), Sequence('snapshot_id_seq'), primary_key=True)
    sequence_id = Column(UUIDType(), index=True)
    position = Column(BigInteger(), index=True)
    topic = Column(String(255))
    data = Column(Text())
    __table_args__ = UniqueConstraint('sequence_id', 'position',
                                      name='integer_sequenced_item_uc'),


datastore.setup_tables()

```

We can also introduce a snapshotting policy, so that a snapshot is automatically taken every five events.

```python
from eventsourcing.infrastructure.eventplayer import EventPlayer
from eventsourcing.domain.model.events import unsubscribe


class SnapshottingPolicy(object):

    def __init__(self, event_player):
        assert isinstance(event_player, EventPlayer)
        self.event_player = event_player
        subscribe(predicate=self.requires_snapshot, handler=self.take_snapshot)
    
    @staticmethod
    def requires_snapshot(event):
        if not isinstance(event, DomainEvent):
            return False
        if isinstance(event, Discarded):
            return False
        return not (event.entity_version + 1) % 5

    def take_snapshot(self, event):
        self.event_player.take_snapshot(event.entity_id)
        
    def close(self):
        unsubscribe(predicate=self.requires_snapshot, handler=self.take_snapshot)
```

The application also needs a policy to persist snapshots that are taken.


```python
from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.infrastructure.snapshotting import EventSourcedSnapshotStrategy
from eventsourcing.domain.model.snapshot import Snapshot


class ApplicationWithSnapshotting(object):

    def __init__(self, datastore):
        self.event_store = EventStore(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                datastore=datastore,
                active_record_class=SequencedItemTable,
                sequenced_item_class=SequencedItem,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name='entity_id',
                position_attr_name='entity_version',
            )
        )
        self.snapshot_store = EventStore(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                datastore=datastore,
                active_record_class=SnapshotTable,
                sequenced_item_class=SequencedItem,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name='entity_id',
                position_attr_name='entity_version',
            )
        )
        self.snapshot_strategy = EventSourcedSnapshotStrategy(
            event_store=self.snapshot_store,
        )
        self.example_repository = EventSourcedRepository(
            event_store=self.event_store,
            snapshot_strategy=self.snapshot_strategy,
            mutator=mutate,
        )
        self.entity_persistence_policy = PersistencePolicy(self.event_store, event_type=DomainEvent)
        self.snapshot_persistence_policy = PersistencePolicy(self.snapshot_store, event_type=Snapshot)
        self.snapshotting_policy = SnapshottingPolicy(self.example_repository.event_player)
        
    def create_example(self, foo):
        return create_new_example(foo=foo)
        
    def close(self):
        self.entity_persistence_policy.close()
        self.snapshot_persistence_policy.close()
        self.snapshotting_policy.close()

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
```

Now snapshots of example entities will be taken every five events, except for the initial event and discarded events.

```python
with ApplicationWithSnapshotting(datastore) as app:

    entity = app.create_example(foo='bar1')
    
    assert entity.id in app.example_repository
    
    assert app.example_repository[entity.id].foo == 'bar1'
    
    entity.foo = 'bar2'
    entity.foo = 'bar3'
    entity.foo = 'bar4'

    assert app.example_repository.event_player.get_snapshot(entity.id) is None

    entity.foo = 'bar5'

    assert app.example_repository.event_player.get_snapshot(entity.id) is not None

    entity.foo = 'bar6'
    entity.foo = 'bar7'
    
    assert app.example_repository[entity.id].foo == 'bar7'
    
    assert app.example_repository.event_player.get_snapshot(entity.id).state['_foo'] == 'bar5'

    # Discard the entity.    
    entity.discard()
    assert entity.id not in app.example_repository
    
    try:
        app.example_repository[entity.id]
    except KeyError:
        pass
    else:
        raise Exception('KeyError was not raised')
```

### Step 5: Application-level encryption

To enable encryption, pass in a cipher strategy object when constructing
the sequenced item mapper, and set ```always_encrypt``` to a True value.

```python
class EncryptedApplication(object):

    def __init__(self, datastore, cipher):
        self.event_store = EventStore(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                datastore=datastore,
                active_record_class=SequencedItemTable,
                sequenced_item_class=SequencedItem,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name='entity_id',
                position_attr_name='entity_version',
                always_encrypt=True,
                cipher=cipher,
            )
        )
        self.example_repository = EventSourcedRepository(
            event_store=self.event_store,
            mutator=mutate,
        )
        self.persistence_policy = PersistencePolicy(self.event_store, event_type=DomainEvent)
        
    def create_example(self, foo):
        return create_new_example(foo=foo)
        
    def close(self):
        self.persistence_policy.close()

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
```

You can use the AES cipher strategy provided by this library. Alternatively,
you can craft your own cipher strategy object.

Event attribute values are encrypted inside the application before they are mapped
to the database. The values are decrypted before domain events are replayed.

```python
from eventsourcing.domain.services.aes_cipher import AESCipher

aes_key = '0123456789abcdef'

with EncryptedApplication(datastore, cipher=AESCipher(aes_key)) as app:

    secret_entity = app.create_example(foo='secret info')

    # Without encryption, application state is visible in the database.
    item1 = app.event_store.active_record_strategy.get_item(entity.id, 0)
    assert 'bar1' in item1.data
    
    # With encryption enabled, application state is not visible in the database. 
    item2 = app.event_store.active_record_strategy.get_item(secret_entity.id, 0)
    assert 'secret info' not in item2.data
    
    # Events are decrypted inside the application.
    retrieved_entity = app.example_repository[secret_entity.id]
    assert 'secret info' in retrieved_entity.foo    
```


### Step 6: Optimistic concurrency control

With the application above, because of the unique constraint
on the SQLAlchemy table, it isn't possible to branch the
evolution of an entity and store two events at the same version.

Hence, if the entity you are working on has been updated elsewhere,
an attempt to update your object will raise a concurrency exception.

```python
from eventsourcing.exceptions import ConcurrencyError

with Application(datastore) as app:

    entity = app.create_example(foo='bar1')

    a = app.example_repository[entity.id]
    b = app.example_repository[entity.id]
    
    # Change the entity using instance 'a'.
    a.foo = 'bar2'
    
    # Because 'a' has been changed since 'b' was obtained,
    # 'b' cannot be updated unless it is firstly refreshed.
    try:
        b.foo = 'bar3'
    except ConcurrencyError:
        pass
    else:
        raise Exception("Failed to control concurrency of 'b'.")
      
    # Refresh object 'b', so that 'b' has the current state of the entity.
    b = app.example_repository[entity.id]
    assert b.foo == 'bar2'

    # Changing the entity using instance 'b' now works because 'b' is up to date.
    b.foo = 'bar3'
    assert app.example_repository[entity.id].foo == 'bar3'
    
    # Now 'a' does not have the current state of the entity, and cannot be changed.
    try:
        a.foo = 'bar4'
    except ConcurrencyError:
        pass
    else:
        raise Exception("Failed to control concurrency of 'a'.")
```


### Step 7: Alternative database schema

Let's say we want the database table to look like stored events, rather than sequenced items.

It's easy to do. Just define a new sequenced item class, e.g. ```StoredEvent``` below.

```python
from collections import namedtuple

StoredEvent = namedtuple('StoredEvent', ['aggregate_id', 'aggregate_version', 'event_type', 'state'])
```

Then define a suitable active record class.

```python
class StoredEventTable(Base):
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
```

Then redefine the application class to use the two new classes.

```python
class Application(object):
    def __init__(self, datastore):
        self.event_store = EventStore(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                datastore=datastore,
                active_record_class=StoredEventTable,
                sequenced_item_class=StoredEvent,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=StoredEvent,
                sequence_id_attr_name='entity_id',
                position_attr_name='entity_version',
            )
        )
        self.example_repository = EventSourcedRepository(
            event_store=self.event_store,
            mutator=mutate,
        )
        self.persistence_policy = PersistencePolicy(self.event_store, event_type=DomainEvent)
        
    def create_example(self, foo):
        return create_new_example(foo=foo)
        
    def close(self):
        self.persistence_policy.close()

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
```

Set up the database again.

```python
datastore = SQLAlchemyDatastore(
    base=Base,
    settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
    tables=(StoredEventTable,),
)

datastore.setup_connection()
datastore.setup_tables()
```

Then you can use the application as before.

```python
with Application(datastore) as app:

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
```


### Step 8: Using Cassandra

Using Cassandra is very similar to using SQLAlchemy. Please note, it isn't necessary to pass
the Cassandra datastore object into the active record strategy object.

```python
from eventsourcing.infrastructure.cassandra.datastore import CassandraSettings, CassandraDatastore
from eventsourcing.infrastructure.cassandra.activerecords import CqlIntegerSequencedItem
from eventsourcing.infrastructure.cassandra.activerecords import CassandraActiveRecordStrategy

cassandra_datastore = CassandraDatastore(
    settings=CassandraSettings(),
    tables=(CqlIntegerSequencedItem,),
)

cassandra_datastore.setup_connection()
cassandra_datastore.setup_tables()


class ApplicationWithCassandra(object):
    def __init__(self):
        self.event_store = EventStore(
            active_record_strategy=CassandraActiveRecordStrategy(
                active_record_class=CqlIntegerSequencedItem,
                sequenced_item_class=SequencedItem,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                sequenced_item_class=SequencedItem,
                sequence_id_attr_name='entity_id',
                position_attr_name='entity_version',
            )
        )
        self.example_repository = EventSourcedRepository(
            event_store=self.event_store,
            mutator=mutate,
        )
        self.persistence_policy = PersistencePolicy(self.event_store, event_type=DomainEvent)
        
    def create_example(self, foo):
        return create_new_example(foo=foo)
        
    def close(self):
        self.persistence_policy.close()

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


with ApplicationWithCassandra() as app:

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
```

### Step 9: Aggregates in domain driven design
  
Let's say we want to separate the sequence of events from entities, and instead have
an aggregate that controls a set of entities.

We can define some "aggregate events" which have ```aggregate_id``` and
```aggregate_version```. And we can rework the entity class to function as a root
entity of the aggregate.

In the example below, the aggregate class has a list of pending events, and a ```save()```
method that publishes all pending events. The other operations append events to the list
of pending events, rather than publishing them individually.

The library supports appending multiple events to the event store in
a single atomic transaction.

The entity factory is now a method of the aggregate, and the aggregate's mutator is capable
of mutating the aggregate's entities.

```python
class AggregateEvent(object):
    """Layer supertype."""

    def __init__(self, aggregate_id, aggregate_version, timestamp=None, **kwargs):
        self.aggregate_id = aggregate_id
        self.aggregate_version = aggregate_version
        self.timestamp = timestamp or time.time()
        self.__dict__.update(kwargs)


class AggregateCreated(AggregateEvent):
    """Published when an aggregate is created."""
    def __init__(self, aggregate_version=0, **kwargs):
        super(AggregateCreated, self).__init__(aggregate_version=aggregate_version, **kwargs)


class EntityCreated(AggregateEvent):
    """Published when an entity is created."""
    def __init__(self, entity_id, **kwargs):
        super(EntityCreated, self).__init__(entity_id=entity_id, **kwargs)


class AggregateDiscarded(AggregateEvent):
    """Published when an aggregate is discarded."""
    def __init__(self, **kwargs):
        super(AggregateDiscarded, self).__init__(**kwargs)


class ExampleAggregateRoot():
    """Example root entity."""
    def __init__(self, aggregate_id, aggregate_version=0, timestamp=None):
        self._id = aggregate_id
        self._version = aggregate_version
        self._is_discarded = False
        self._created_on = timestamp
        self._last_modified_on = timestamp
        self._pending_events = []
        self._entities = {}

    @property
    def id(self):
        return self._id

    @property
    def version(self):
        return self._version

    @property
    def is_discarded(self):
        return self._is_discarded

    @property
    def created_on(self):
        return self._created_on

    @property
    def last_modified_on(self):
        return self._last_modified_on

    def count_entities(self):
        return len(self._entities)
        
    def create_new_entity(self):
        assert not self._is_discarded
        event = EntityCreated(
            entity_id=uuid.uuid4(),
            aggregate_id=self.id,
            aggregate_version=self.version,
        )
        mutate_aggregate_event(self, event)
        self._pending_events.append(event)

    def discard(self):
        assert not self._is_discarded
        event = AggregateDiscarded(aggregate_id=self.id, aggregate_version=self.version)
        mutate_aggregate_event(self, event)
        self._pending_events.append(event)
        
    def save(self):
        publish(self._pending_events[:])
        self._pending_events = []


def mutate_aggregate_event(aggregate, event):
    """Mutator function for example aggregate root."""

    # Handle "created" events by instantiating the aggregate class.
    if isinstance(event, AggregateCreated):
        aggregate = ExampleAggregateRoot(**event.__dict__)
        aggregate._version += 1
        return aggregate
        
    # Handle "entity created" events by adding a new entity to the aggregate's dict of entities.
    elif isinstance(event, EntityCreated):
        assert not aggregate.is_discarded
        entity = Example(entity_id=event.entity_id)
        aggregate._entities[entity.id] = entity
        aggregate._version += 1
        aggregate._last_modified_on = event.timestamp
        return aggregate
        
    # Handle "discarded" events by returning 'None'.
    elif isinstance(event, AggregateDiscarded):
        assert not aggregate.is_discarded
        aggregate._version += 1
        aggregate._is_discarded = True
        return None
    else:
        raise NotImplementedError(type(event))


class DDDApplication(object):
    def __init__(self, datastore):
        self.event_store = EventStore(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                datastore=datastore,
                active_record_class=StoredEventTable,
                sequenced_item_class=StoredEvent,
            ),
            sequenced_item_mapper=SequencedItemMapper(StoredEvent)
        )
        self.aggregate_repository = EventSourcedRepository(
            event_store=self.event_store,
            mutator=mutate_aggregate_event,
        )
        self.persistence_policy = PersistencePolicy(self.event_store, event_type=AggregateEvent)
        
    def create_example_aggregate(self):
        event = AggregateCreated(aggregate_id=uuid.uuid4())
        aggregate = mutate_aggregate_event(aggregate=None, event=event)
        aggregate._pending_events.append(event)
        return aggregate
        
    def close(self):
        self.persistence_policy.close()

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


with DDDApplication(datastore) as app:

    # Create a new aggregate.
    aggregate = app.create_example_aggregate()
    aggregate.save()

    # Check it exists in the repository.
    assert aggregate.id in app.aggregate_repository, aggregate.id

    # Check the aggregate has zero entities.
    assert aggregate.count_entities() == 0
    
    # Check the aggregate has zero entities.
    assert aggregate.count_entities() == 0
    
    # Ask the aggregate to create an entity within itself.
    aggregate.create_new_entity()

    # Check the aggregate has one entity.
    assert aggregate.count_entities() == 1
    
    # Check the aggregate in the repo still has zero entities.
    assert app.aggregate_repository[aggregate.id].count_entities() == 0
    
    # Call save().
    aggregate.save()
    
    # Check the aggregate in the repo now has one entity.
    assert app.aggregate_repository[aggregate.id].count_entities() == 1
    
    # Create two more entities within the aggregate.
    aggregate.create_new_entity()
    aggregate.create_new_entity()
    
    # Save both "entity created" events in one atomic transaction.
    aggregate.save()
    
    # Check the aggregate in the repo now has three entities.
    assert app.aggregate_repository[aggregate.id].count_entities() == 3
    
    # Discard the aggregate, but don't call save() yet.
    aggregate.discard()
    
    # Check the aggregate still exists in the repo.
    assert aggregate.id in app.aggregate_repository

    # Call save().
    aggregate.save()

    # Check the aggregate no longer exists in the repo.
    assert aggregate.id not in app.aggregate_repository
```


## Design

The design of the library follows the layered architecture: interfaces, application, domain, and infrastructure.

The domain layer contains a model of the supported domain, and services that depend on that
model. The infrastructure layer encapsulates the infrastructural services required by the application.

The application is responsible for binding domain and infrastructure, and has policies
such as the persistence policy, which stores domain events whenever they are published by the model.

The example application has an example respository, from which example entities can be retrieved. It
also has a factory method to register new example entities. Each repository has an event player, which all share
an event store with the persistence policy. The persistence policy uses the event store
to store domain events, and the event players use the event store to retrieve the stored events. The event
players also share with the model the mutator functions that are used to apply domain events to an initial state.

Functionality such as mapping events to a database, or snapshotting, is factored as strategy objects and injected
into dependents by constructor parameter. Application level encryption is a mapping option.

The sequenced item persistence model allows domain events to be stored in wide variety of database 
services, and optionally makes use of any optimistic concurrency controls the database system may afford.

![UML Class Diagram](https://www.lucidchart.com/publicSegments/view/098200e1-0ca9-4660-be7f-11f8f13a2163/image.png)


## Background

Although the event sourcing patterns are each quite simple, and they can be reproduced in code for each project,
they do suggest cohesive mechanisms, for example applying and publishing the events generated within domain
entities, storing and retrieving selections of the events in a highly scalable manner, replaying the stored
events for a particular entity to obtain the current state, and projecting views of the event stream that are
persisted in other models. Quoting from the "Cohesive Mechanism" pages in Eric Evan's Domain Driven Design book:

_"Therefore: Partition a conceptually COHESIVE MECHANISM into a separate lightweight framework. Particularly watch
for formalisms for well-documented categories of algorithms. Expose the capabilities of the framework
with an INTENTION-REVEALING INTERFACE. Now the other elements of the domain can focus on expressing the problem
("what"), delegating the intricacies of the solution ("how") to the framework."_

The example usage (see above) introduces the "interface". The "intricacies" can be found in the source code.

Inspiration:

* Martin Fowler's article on event sourcing
    * http://martinfowler.com/eaaDev/EventSourcing.html

* Greg Young's discussions about event sourcing, and EventStore system
    * https://www.youtube.com/watch?v=JHGkaShoyNs
    * https://www.youtube.com/watch?v=LDW0QWie21s
    * https://dl.dropboxusercontent.com/u/9162958/CQRS/Events%20as%20a%20Storage%20Mechanism%20CQRS.pdf
    * https://geteventstore.com/

* Robert Smallshire's brilliant example code on Bitbucket
    * https://bitbucket.org/sixty-north/d5-kanban-python/src

* Various professional projects that called for this approach, across which I didn't want to rewrite
  the same things each time


See also:

* 'Evaluation of using NoSQL databases in an event sourcing system' by Johan Rothsberg
    * http://www.diva-portal.se/smash/get/diva2:877307/FULLTEXT01.pdf

* Wikipedia page on Object-relational impedance mismatch
    * https://en.wikipedia.org/wiki/Object-relational_impedance_mismatch


## Upgrade notes

### Upgrading from 1.x to 2.x

Version 2 departs from version 1 by using sequenced items as the persistence model (was stored events
in version 1). This makes version 2 incompatible with version 1. However, with a little bit of code
it would be possible to rewrite all existing stored events from version 1 into the version 2 sequenced
items, since the attribute values are broadly the same. If you need help with this, please get in touch.


## Project

This project is hosted on GitHub.

* https://github.com/johnbywater/eventsourcing


Questions, requests and any other issues can be registered here:

* https://github.com/johnbywater/eventsourcing/issues
