# Event Sourcing in Python

[![Build Status](https://secure.travis-ci.org/johnbywater/eventsourcing.png?branch=develop)](https://travis-ci.org/johnbywater/eventsourcing)
[![Coverage Status](https://coveralls.io/repos/github/johnbywater/eventsourcing/badge.svg?branch=develop#123)](https://coveralls.io/github/johnbywater/eventsourcing?branch=develop)
[![Gitter chat](https://badges.gitter.im/gitterHQ/services.png)](https://gitter.im/eventsourcing-in-python/eventsourcing)

A library for event sourcing in Python.


## Install

Use pip to install the [latest distribution](https://pypi.python.org/pypi/eventsourcing) from
the Python Package Index.

    pip install eventsourcing

If you want to use SQLAlchemy, then please install with 'sqlalchemy' optional extra.

    pip install eventsourcing[sqlalchemy]

Similarly, if you want to use Cassandra, then please install with 'cassandra'.

    pip install eventsourcing[cassandra]

If you want to run the test suite, or try the example below with different backends, then
please install with the 'test' optional extra.

    pip install eventsourcing[test]

After installing with 'test', the test suite should pass.

    python -m unittest discover eventsourcing.tests -v

Please register any [issues on GitHub](https://github.com/johnbywater/eventsourcing/issues).

There is also a []mailing list](https://groups.google.com/forum/#!forum/eventsourcing-users).
And a [room on Gitter](https://gitter.im/eventsourcing-in-python/eventsourcing)


## Overview

This library supports event sourcing in Python.

One definition of event sourcing suggests the state of an event sourced application
is determined by a sequence of events. Another definition has event
sourcing as a persistence mechanism for domain driven design.

It is common for the state of a software application state to be distributed or partitioned
across a set of entities or "models". Therefore, this library provides mechanisms useful in
such an application that is event soured: a style for coding entity behaviours to instantiate
and publishe domain events; and a way for the domain events of an entity to be stored and replayed to
obtain the state of the entity on demand.

    This document highlights the main features of the library, provides instructions for installing
the package, includes a detailed example of usage, describes the design of the software, and has
some background information about the project.


## Features

**Event Store** — Appends and retrieves domain events. The event store uses
a stored event repository to append and retrieve stored events. The event store uses a
transcoder to serialise and deserialise domain events as store events. The library has a
number of different stored event repositories that adapt a variety of ORMs and
databases systems (e.g. SQLAlchemy, Cassandra). If your database system isn't
already supported, it will be easy to adapt with a custom stored event repository.

**Event Player** — Use the event store to retrieve domain events. An event player
reconstitutes entities of a particular type from their domain events, optionally with
snapshotting. Snapshotting avoids replaying an entire event stream to obtain
the current state of an entity. A snapshot strategy is included which reuses
the capabilities of this library by implementing snapshots as domain events. It can
easily be substituted with a strategy that, for example, uses a dedicated table for snapshots.

**Persistence Policy** - Subscribes to receive published domain events.
Appends the domain events to the event store whenever a domain event is
published. Domain events are typically published by the methods of an entity.

**Synchronous Publish-Subscribe Mechanism** — Stable and deterministic,
with handlers called in the order they are registered, and with which
calls to publish events do not return until all event subscribers have
returned. In general, subscribers are policies of the application, which may 
execute further commands whenever an particular kind of event is received.
Publishers of domain events are typically the methods of an entity.

**Customizable Datastore** — Flexible mapping between domain events and sequenced
items, and between sequenced items and your database. Allows support to be added for
serialization and deserialization of custom value object types.

**Application-Level Encryption** — Symmetric encryption of stored
events, including snapshots and logged messages, using a customizable
cipher. Can be used to encrypt some events, or all events, or not applied at
all (the default). Included is an AES cipher strategy, by default in CBC mode
with 128 bit blocksize, that uses a 16 byte encryption key passed in at run time,
and which generates a unique 16 byte initialization vector for each encryption.
In this cipher, data is compressed before it is encrypted, which can mean application
performance is surprisingly improved when encryption is enabled.

**Optimistic Concurrency Control** — Can be used to ensure a distributed or
horizontally scaled application doesn't become inconsistent due to concurrent
method execution. Leverages any optimistic concurrency controls in the database adapted
by the stored event repository. With Cassandra, this can accomplish linearly-scalable
distributed optimistic concurrency control, guaranteeing sequential consistency of an
event stream, across a distributed application. It is also possible to serialize calls
to the methods of an entity, but that is currently out of the scope of this package -
if you wish to do that, perhaps something like [Zookeeper](https://zookeeper.apache.org/)
might help.

**Abstract Base Classes** — For application objects, event soured domain entities,
domain entity repositories, domain events, mapping strategies, snapshotting strategies,
test cases, etc. These classes are at least suggestive of how to structure an event sourced
application, and can be used directly to extend this library for your own purposes.

**Worked Examples** — A simple worked example application (see below), with example
entity class, example event sourced repository, and example factory method.


## Usage

This section describes how to write a simple event sourced application. To create
a working program, you can copy and paste the following code snippets into a single
Python file.

This example follows the layered architecture: application, domain, and infrastructure.

The code snippets in this section have been tested. You may experiment by making
variations. If you installed the library into a Python virtualenv, please
check that your virtualenv is activated before running your program.


#### Step 1: domain model

Let's start with the domain model. Because the state of an event sourced application
is determined by a sequence of events, we need to define some events.

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
    """Raised when an entity is created."""
    def __init__(self, **kwargs):
        super(Created, self).__init__(entity_version=0, **kwargs)

    
class ValueChanged(DomainEvent):
    """Raised when a named value is changed."""
    def __init__(self, name, value, **kwargs):
        super(ValueChanged, self).__init__(**kwargs)
        self.name = name
        self.value = value

    
class Discarded(DomainEvent):
    """Raised when an entity is discarded."""
    
```

Please note, these classes do not depend on the library. However, the library does contain
a collection of different kinds of domain events clasees that you can use in your models,
for example the ```AggregateEvent```.

Now, let's use the events classes above to define an "example" entity.

The ```Example```entity class below has an entity ID, a version number, and a
timestamp. It also has a property ```foo```, and a ```discard()``` method to use
when the entity is discarded. The factory method ```create_new_example()``` can
be used to create new entities.

All the methods follow a similar pattern. They construct an event that represents the result
of the operation. They use a "mutator function" function ```mutate()``` to apply the event
to the entity. And they "publish" the event for the benefit of any subscribers.

When replaying a sequence of events, a "mutator function" is commonly
used to apply an event to an initial state. For the sake of simplicity
in this example, we'll use an if-else block that can handle the different
types of events.


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
        event = ValueChanged(
            entity_id=self.id,
            entity_version=self.version,
            name='foo',
            value=value,
        )
        mutate(self, event)
        publish(event)

    def discard(self):
        assert not self._is_discarded
        event = Discarded(entity_id=self.id, entity_version=self.version)
        mutate(self, event)
        publish(event)


def create_new_example(foo):
    """Factory method for Example entities."""

    # Create an entity ID.
    entity_id = uuid.uuid4().hex
    
    # Instantiate a domain event.
    event = Created(entity_id=entity_id, foo=foo)
    
    # Mutate the event to construct the entity.
    entity = mutate(None, event)
    
    # Publish the domain event.
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
    # Handle "attribute changed" events by setting the named value.
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

We can now create a new example entity. We can update its property ```foo```. And we can discard
the entity using the ```discard()``` method.

Let's subscribe to receive the events that will be published, so we can see what is happening.

```python
from eventsourcing.domain.model.events import subscribe

# A list of received events.
received_events = []

# Subscribe to receive published events.
subscribe(lambda e: received_events.append(e))

# Create a new entity using the factory.
entity1 = create_new_example(foo='bar1')

# Check the entity has an ID.
assert entity1.id

# Check the entity has a version number.
assert entity1.version == 1

# Check the received events.
assert len(received_events) == 1, received_events
assert isinstance(received_events[0], Created)
assert received_events[0].entity_id == entity1.id
assert received_events[0].entity_version == 0
assert received_events[0].foo == 'bar1'

# Check the value of property 'foo'.
assert entity1.foo == 'bar1'

# Update property 'foo'.
entity1.foo = 'bar2'

# Check the new value of 'foo'.
assert entity1.foo == 'bar2'

# Check the version number has increased.
assert entity1.version == 2

# Check the received events.
assert len(received_events) == 2, received_events
assert isinstance(received_events[1], ValueChanged)
assert received_events[1].entity_version == 1
assert received_events[1].name == 'foo'
assert received_events[1].value == 'bar2'
```

This example uses the library's ```publish()``` and ```subscribe()``` functions, but you could
easily use your own publish-subscribe implementation.


#### Step 2: infrastructure

Since the application state is determined by a sequence of events, the events of the
entities of the application must somehow be stored.

Let's start by setting up a database for storing events. For the sake of simplicity in this
example, use SQLAlchemy to define a database that stores integer-sequenced items.

```python
from sqlalchemy.ext.declarative.api import declarative_base
from sqlalchemy.sql.schema import Column, Sequence, UniqueConstraint
from sqlalchemy.sql.sqltypes import BigInteger, Integer, String, Text


Base = declarative_base()


class IntegerSequencedItem(Base):
    __tablename__ = 'integer_sequenced_items'

    id = Column(Integer, Sequence('integer_sequened_item_id_seq'), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = Column(String(255), index=True)

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

Now create the database and tables. The SQLAlchemy objects are adapted with classes from the 
library, which provide a common interface for required operations.

```python
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemySettings, SQLAlchemyDatastore

datastore = SQLAlchemyDatastore(
    base=Base,
    settings=SQLAlchemySettings(uri='sqlite:///:memory:'),
    tables=(IntegerSequencedItem,),
)

datastore.setup_connection()
datastore.setup_tables()
```

We want to retrieve whole entities, rather than merely a sequence of events. So let's
define an event sourced repository for the example entity class, since it is common to retrieve 
entities from a repository.

```python
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository

class ExampleRepository(EventSourcedRepository):
    domain_class = Example
```

The event sourced repository needs an event store to save and retrieve domain
events.

To support different kinds of sequences, and allow for different schemas,
the event store has been designed to use a sequenced item mapper to map domain events
into sequenced items.

The event store also uses an active record strategy to map between sequenced
items and a table in a database.

The details have been made explicit so they can be easily replaced.

```python
from eventsourcing.infrastructure.eventstore import EventStore
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy
from eventsourcing.infrastructure.transcoding import SequencedItemMapper

active_record_strategy = SQLAlchemyActiveRecordStrategy(
    datastore=datastore,
    active_record_class=IntegerSequencedItem,
)

event_store = EventStore(
    active_record_strategy=active_record_strategy,
    sequenced_item_mapper=SequencedItemMapper(
        position_attr_name='entity_version',
    )
)

example_repository = ExampleRepository(
    event_store=event_store,
    mutator=mutate,
)
```

Now, let's write all the events we subscribed to earlier into the event store.

```python
for event in received_events:
    event_store.append(event)

stored_events = event_store.get_domain_events(entity1.id)
assert len(stored_events) == 2, (received_events, stored_events)
```

The entity can now be retrieved from the repository, using its dictionary-like interface.

```python

retrieved_entity = example_repository[entity1.id]
assert retrieved_entity.foo == 'bar2'
```

The example above uses an SQLite in memory relational database, but you
could change 'uri' to any valid connection string. Here are some example
connection strings: for an SQLite file; for a PostgreSQL database; and
for a MySQL database. See SQLAlchemy's create_engine() documentation for details.

```
sqlite:////tmp/mydatabase

postgresql://scott:tiger@localhost:5432/mydatabase

mysql://scott:tiger@hostname/dbname
```

Similar to the support for storing events in SQLAlchemy, there
are classes in the library for Cassandra. Support for other
databases is forthcoming.


#### Step 3: application

The application layer brings together the domain and the infrastructure.

The application has an event store, and can have entity repositories.

Most importantly, the application has a persistence policy. The persistence
policy firstly subscribes to receive events when they are published, and it
uses the event store to store all the events that it receives.

```python
from eventsourcing.application.policies import PersistencePolicy

class Application(object):

    def __init__(self, datastore):
        self.event_store = EventStore(
            active_record_strategy=SQLAlchemyActiveRecordStrategy(
                datastore=datastore,
                active_record_class=IntegerSequencedItem,
            ),
            sequenced_item_mapper=SequencedItemMapper(
                position_attr_name='entity_version',
            )
        )
        self.example_repository = ExampleRepository(
            event_store=self.event_store,
            mutator=mutate,
        )
        self.persistence_policy = PersistencePolicy(self.event_store)
        
    def create_example(self, foo):
        return create_new_example(foo=foo)
```

After instatiating the application, we can create more example entities
and expect they will be available in the repository immediately.

```python
app = Application(datastore)

entity2 = app.create_example(foo='bar3')
entity3 = app.create_example(foo='bar4')

assert entity2.id in app.example_repository
assert entity3.id in app.example_repository

assert app.example_repository[entity2.id].foo == 'bar3'
assert app.example_repository[entity3.id].foo == 'bar4'

entity2.foo = 'bar5'
entity3.foo = 'bar6'

assert app.example_repository[entity2.id].foo == 'bar5'
assert app.example_repository[entity3.id].foo == 'bar6'
```

A discarded entity can not be retrieved from the repository. The repository's
dictionary-like interface raises a Python key error whenever an attempt is made to get
 an entity that has been discarded.

```python
entity2.discard()
assert entity2.id not in app.example_repository

try:
    app.example_repository[entity2.id]
except KeyError:
    pass
else:
    raise Exception('KeyError was not raised')
```

Congratulations. You have created yourself an event sourced application.


Todo: optimistic concurrency control
Todo: encryption


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

The sequnced item persistence model allows domain events to be stored in wide variety of database 
services, and optionally makes use of any optimistic concurrency controls the database system may afford.


![UML Class Diagram](https://www.lucidchart.com/publicSegments/view/9919fa7f-2c6d-4aac-b189-5f2871a69aee/image.png)




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


## Forthcoming Features

**Boxes (forthcoming, experimental)**
The notification log pattern enables a flow of events between applications
in different bounded contexts, and suggests an effective way of avoiding a monolithic
application by developing a suite of smaller, collaborating, event driven
and event sourced applications that can maintain integrity despite premature
application termination and occasional network partitioning. "Box" is this project's working
name for the archetypal event sourced application that is dedicated to a bounded context,
whilst also being capable of collaborating (using notifications) with other such application
in other bounded contexts. The well factored monolith amounts to having all boxes running in
one container, with notifications being made synchronously in process. Microservices arise
simply from moving a box to a new container, with notifications then propagated across the
process boundaries. As Eric Evans has suggested, harder social boundaries are perhaps a necessary
condition to ensure a domain driven design can be a socially successful design, due to the rough
and tumble of day-to-day software development, and the fact that software developers double in
number every five years, so that on average half the programmers have less than five years
experience, which might not be enough adequately to practise design approaches such as DDD.

* List-based collections (forthcoming)

* Stored event repository to persist stored events in a file using a
 very simple file format (forthcoming)

* Stored event repository to persist stored events using MongoDB (forthcoming)

* Stored event repository to persist stored events using HBase (forthcoming)

* Stored event repository to persist stored events using DynamoDB (forthcoming)

* Method to delete all domain events for given domain entity ID (forthcoming)

* Method to get all domain events in the order they occurred (forthcoming)

* Storage retries and fallback strategies, to protect against failing to write an event (forthcoming)

* Subscriber that publishes domain events to RabbitMQ (forthcoming)

* Subscriber that publishes domain events to Amazon SQS (forthcoming)

* Republisher that subscribes to RabbitMQ and publishes domain events locally (forthcoming)

* Republisher that subscribers to Amazon SQS and publishes domain event locally (forthcoming)

* Linked pages of domain events ("Archived Timebucketedlog"), to allow event sourced projections easily to make sure they have
all the events (forthcoming)

* Base class for event sourced projections or views (forthcoming)

    * In memory event sourced projection, which needs to replay entire event stream when system starts up (forthcoming)

    * Persistent event sourced projection, which stored its projected state, but needs to replay entire event stream
      when initialized  (forthcoming)

* Event sourced indexes, as persisted event source projections, to discover extant entity IDs (forthcoming)

* Event pointer, to refer to an event in a stream (forthcoming)

* Updating stored events, to support domain model migration (forthcoming)

* Something to store serialized event attribute values separately from the other event information, to prevent large
attribute values inhibiting performance and stability - different sizes could be stored in different ways...
(forthcoming)

* Different kinds of stored event
    * IDs generated from content, e.g. like Git (forthcoming)
    * cryptographically signed stored events (forthcoming)

* Branch and merge mechanism for domain events (forthcoming)

* Support for asynchronous I/O, with an application that uses an event loop (forthcoming)

* More examples (forthcoming)

* Great documentation! (forthcoming)

* Context maps (so we can use univerally unique IDs within a context,
  even though entities arise from other contexts and may not have
  universally unique IDs e.g. integer sequences)

* Optionally decouple topics from actual code, so classes can be moved.


## Upgrade Notes

### Upgrading From 1.x to 2.x

Version 2 departs from version 1 by using sequenced items as the persistence model (was stored events
in version 1). This makes version 2 incompatible with version 1. However, with a little bit of code
it would be possible to rewrite all existing stored events from version 1 into the version 2 sequenced
items, since the attribute values are broadly the same. If you need help with this, please get in touch.


## Project

This project is hosted on GitHub.

* https://github.com/johnbywater/eventsourcing


Questions, requests and any other issues can be registered here:

* https://github.com/johnbywater/eventsourcing/issues
