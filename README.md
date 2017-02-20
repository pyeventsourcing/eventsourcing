# Event Sourcing in Python

[![Build Status](https://secure.travis-ci.org/johnbywater/eventsourcing.png?branch=develop)]
(https://travis-ci.org/johnbywater/eventsourcing)
[![Gitter chat](https://badges.gitter.im/gitterHQ/services.png)](https://gitter.im/eventsourcing-in-python/eventsourcing)

A library for event sourcing in Python.


## Features

**Domain Events, Entities, Repositories, and Subscribers** — Base classes
make it easy to develop new applications with custom entities, custom
repositories, custom domain events, custom subscribers, custom
transcoders, custom stored event repositories, custom snapshotting
mechanism. See example below, and the package's test suite.

**Event Store** — With extendable set of stored event repositories
for adapting different ORMs and databases systems (e.g. Cassandra,
SQLAlchemy). Includes an in-memory stored event
repository implemented with simple Python objects. If your
database system isn't already supported, it will be easy to adapt
with a custom stored event repository.

**Event Player with Snapshots** — Avoid replaying an entire event stream to obtain the
current state of an entity. Makes entity access constant time,
rather than proportional to the number of events. Snapshotting is
implemented as a strategy object in the application class, making it
easy to use a custom snapshotting mechanism and storage. A snapshot
strategy is included which reuses the capabilities of this library by
implementing snapshots as domain events.

**Fast Forwarding** — Of entities to latest published event, used with
snapshots and also when optimistic currency control exceptions are
encountered.

**Optimistic Concurrency Control** — Implemented using optimistic
concurrency controls in the adapted database. For example, with
Cassandra this accomplishes linearly-scalable distributed optimistic
concurrency control, guaranteeing sequential consistency of each
event stream, across a distributed application. It is also possible to
serialize the execution of commands on an aggregate, but that is out
of the scope of this package. If you wish to do that, perhaps something
like [Zookeeper](https://zookeeper.apache.org/) might help.

**Application-Level Encryption** — Symmetric encryption of all stored
events, including snapshots and logged messages, using a customizable
cipher. Can optionally be applied to encrypt particular events, or all
stored events, or not applied at all (the default). Included is an AES
cipher, by default in CBC mode with 128 bit blocksize, that uses a 16
byte encryption key passed in at run time, and which generates a
unique 16 byte initialization vector for each encryption. Data is
compressed before it is encrypted, which can mean application
performance is improved when encryption is enabled.

**Time-Bucketed Logs** — Provide a way of writing an indefinitely long
stream of events in a highly scalable manner. Includes log objects,
logged message events and a log reader implemented as a generator that
can span across many many buckets. For example, a domain event log
that allows all stored events in an application to be logged in
a linearly scalable manner, and then retrieved in order, limited by
number, from any point in time until another point in time, in reverse
or ascending order.

**Notification Logs** - Provide a way of reading an indefinitely long
sequence of events in a highly scalable manner. Includes a notification
logger that writes an event sourced log that can be indexed with a
contiguous integer sequence, and a log reader implemented as a generator
that selects a part of a sequence using Python's list slice syntax.

**Customizable Transcoding** — Between domain events and stored events,
allows support to be added for serialization and deserialization of
custom value object types, and also makes it possible to use different
database schemas when developing a custom stored event repository.

**Synchronous Publish-Subscribe Mechanism** — Entirely deterministic,
with handlers called in the order they are registered, and with which
calls to publish events do not return until all event subscribers have
returned.

**Worked Examples** — A simple worked example application, with example
entity class, event sourced repository, and factory method (see below).
Also included is a slightly more sophisticated version of the
example application below.

**Collections** — Event sourced collections, for modelling different
kinds of multiplicity.


## Install

Use pip to install the [latest distribution](https://pypi.python.org/pypi/eventsourcing) from
the Python Package Index.

    pip install eventsourcing

If you want to run the test suite, or try the example below, then
please install with the optional extra called 'test'.

    pip install eventsourcing[test]

After installing with the 'test' optional extra, the test suite should
pass.

    python -m unittest discover eventsourcing.tests -v

Please register any issues you find.

* https://github.com/johnbywater/eventsourcing/issues


There is also a mailing list.

* https://groups.google.com/forum/#!forum/eventsourcing-users


## Usage

Start by opening a new Python file in your favourite editor, or start
a new project in your favourite IDE (I've been using PyCharm for this
code).

Start writing yourself a new event sourced entity class, by making a
subclass of 'EventSourcedEntity' (from module
'eventsourcing.domain.model.entity').

```python
from eventsourcing.domain.model.entity import EventSourcedEntity, mutableproperty


class Example(EventSourcedEntity):
    """An example of an event sourced entity class."""

```

The entity class domain events must be defined on the domain entity
class. In the example below, an 'Example' entity defines 'Created',
'AttributeChanged', and 'Discarded' events. Add these events to your
entity class.

```python
from eventsourcing.domain.model.entity import EventSourcedEntity, mutableproperty


class Example(EventSourcedEntity):
    """An example of an event sourced entity class."""

    class Created(EventSourcedEntity.Created):
        pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged):
        pass

    class Discarded(EventSourcedEntity.Discarded):
        pass

```

When are these events published? The 'Created' event is published by a
factory method (see below), its values are used to initialise an
entity. The 'Discarded' event is published by the discard() method,
which is defined on class 'EventSourcedEntity'.

The 'mutableproperty' decorator is used to define mutable properties
'a' and 'b'. The decorator introduces a setter that generates
'AttributeChanged' events when values are assigned to the properties.

Add the two mutable properties 'a' and 'b' to your entity class.

```python
from eventsourcing.domain.model.entity import EventSourcedEntity, mutableproperty


class Example(EventSourcedEntity):
    """An example of an event sourced entity class."""

    class Created(EventSourcedEntity.Created):
        pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged):
        pass

    class Discarded(EventSourcedEntity.Discarded):
        pass

    @mutableproperty
    def a(self):
        return self._a

    @mutableproperty
    def b(self):
        return self._b
```

That's everything you need to publish domain events. How are they
applied?

The entity class inherits a mutator method that is capable of handling
those events. For example, when a 'Created' event is handled by the
mutator, the attribute values of the Created event object are passed
into the entity class constructor. A factory method will instantiate a
Created event with the attribute values expected by the entity class
constructor.

Add a constructor to your entity class which takes two positional
arguments ('a' and 'b') and keyword arguments ('kwargs') which it
passes through to the base class constructor.


```python
from eventsourcing.domain.model.entity import EventSourcedEntity, mutableproperty


class Example(EventSourcedEntity):
    """An example of an event sourced entity class."""

    class Created(EventSourcedEntity.Created):
        pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged):
        pass

    class Discarded(EventSourcedEntity.Discarded):
        pass

    def __init__(self, a, b, **kwargs):
        super(Example, self).__init__(**kwargs)
        self._a = a
        self._b = b

    @mutableproperty
    def a(self):
        return self._a

    @mutableproperty
    def b(self):
        return self._b

```


Next, define a factory method that returns new entity instances. Rather
than directly constructing the entity object instance, it should
firstly instantiate a 'Created' domain event, and then call the mutator
to obtain an entity object. The factory method then publishes the event
(for example, so that it might be saved into the event store by the
persistence subscriber). Finally it returns the entity to the caller.

```python
from eventsourcing.domain.model.events import publish
import uuid

def register_new_example(a, b):
    entity_id = uuid.uuid4().hex
    event = Example.Created(entity_id=entity_id, a=a, b=b)
    entity = Example.mutate(event=event)
    publish(event=event)
    return entity
```

That's everything needed to create new entities. How can existing
entities be obtained? Entities are retrieved from repositories.

Define an event sourced repository class for your entity. Inherit from
eventsourcing.infrastructure.event_sourced_repo.EventSourcedRepository
and set the 'domain_class' attribute on the subclass.

```python
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository

class ExampleRepository(EventSourcedRepository):

    domain_class = Example
```

Application objects are used to bind domain and infrastructure. This
normally involves having some kind of stored event repository suitable
for the database system you want to use. The stored event repository is
used by the event store, which is used by both the persistence
subscriber to make events durable, and by event players in repositories
to get the events for an entity that has been requested.

Please note, for convenience when using SQLAlchemy or Cassandra to
store events, two application sub-classes are provided:
'EventSourcingWithSQLAlchemy' and 'EventSourcingWithCassandra'.

Add an application class, inheriting from 'EventSourcingWithSQLAlchemy',
that has an event sourced repo. This inheritance provides a
persistence subscriber, an event store, and a stored event repository
that works with SQLAlchemy.


```python
from eventsourcing.application.with_sqlalchemy import EventSourcingWithSQLAlchemy

class ExampleApplication(EventSourcingWithSQLAlchemy):

    def __init__(self, **kwargs):
        super(ExampleApplication, self).__init__(**kwargs)
        self.example_repo = ExampleRepository(
            event_store=self.event_store,
        )

```

For simplicity, this application has just one type of entity. A more
realistic application may involve several different types of entity,
several factory methods, several entity repositories, and different
event sourced projections (mutator funtions).

As shown below, an event sourced application object can be used as a
context manager, which closes the application at the end of the block.

The 'db_uri' arg is used in the application constructor to configure
the database connection. And also a True value for arg 'enable_occ' is
given, so that optimistic concurrency control  is enabled. If you
aren't developing a distributed (or otherwise concurrent and
potentially contentious) application, you don't need to
enable optimistic concurrency control.

With an instance of the example application, call the factory method
register_new_entity() to register a new entity. Then, update an
attribute value by assigning a value. Use the generated entity ID to
subsequently retrieve the registered entity from the repository. Check
the changed attribute value has been stored. Discard the entity and see
that the repository gives a key error when an attempt is made to obtain
the entity after it has been discarded:


```python
db_uri = 'sqlite:///:memory:'
with ExampleApplication(db_uri=db_uri, enable_occ=True) as app:

    # Register a new example.
    example1 = register_new_example(a=1, b=2)

    # Check the example is available in the repo.
    assert example1.id in app.example_repo

    # Check the attribute values.
    entity1 = app.example_repo[example1.id]
    assert entity1.a == 1
    assert entity1.b == 2

    # Change attribute values.
    entity1.a = 123
    entity1.b = 234

    # Check the new values are available in the repo.
    entity1 = app.example_repo[example1.id]
    assert entity1.a == 123
    assert entity1.b == 234

    # Discard the entity.
    entity1.discard()

    assert example1.id not in app.example_repo

    # Getting a discarded entity from the repo causes a KeyError.
    try:
        app.example_repo[example1.id]
    except KeyError:
        pass
    else:
        assert False
```

Congratulations! You have created a new event sourced application.

If you wanted also to enable application-level encryption, pass in a
cipher, and a True value for 'always_encrypt_stored_events'. With
application level encryption, your data below the application will
be encrypted at rest and in transit, which can help prevent data loss.

```python
from eventsourcing.domain.services.cipher import AESCipher

cipher = AESCipher(aes_key='0123456789abcdef')

with ExampleApplication(db_uri=db_uri, enable_occ=True, cipher=cipher,
                        always_encrypt_stored_events=True):

    # Register a new example.
    example1 = register_new_example(a='secret data', b='more secrets')


```

If you want to model other domain events, then simply declare them on
the entity class like the events above, and implement methods on the
entity which instantiate those domain events, apply them to the entity,
publish to subscribers. Add mutator functions to apply the domain
events to the entity objects, for example by directly changing the
internal state of the entity. See the beat_heart() method on the
extended example application included in this distribution.

The example above uses an SQLite in memory relational database, but you
could change 'db_uri' to another connection string if you have a real
database. Here are some example connection strings - for an SQLite file,
for a PostgreSQL database, and for a MySQL database. See SQLAlchemy's
create_engine() documentation for details.

```
sqlite:////tmp/mydatabase

postgresql://scott:tiger@localhost:5432/mydatabase

mysql://scott:tiger@hostname/dbname
```

Todo: Develop above to be a tutorial.


### Upgrading From 1.0.x to 1.1.x

You don't need to do anything. However before using the new optimistic concurrency controls
you will need to migrate an existing database schema to have the new 'entity_versions' table,
and you will also need to add a record to that table for each stored event. See notes in doc
string of EventSourcingApplication class for a zero-downtime migration approach.

To enable optimistic concurrency control, set the application constructor argument named
'enable_occ' to a True value.


### Upgrading From 0.9.4 to 1.0.x

If you are upgrading from version 0.9.4, or earlier, please note that version 0.9.4 is
the last version with ascending as the declared ordering of 'event_id' in column family 'cql_stored_event'.
Subsequent versions have the this ordering declared as descending. The change was made to support both paging
through long histories of events and getting only recent events after a snapshot.

A few things have been renamed, for example '@mutableproperty' is the new name for '@eventsourcedproperty'.
This change was made to reflect the fact that immutable properties are also event sourced.

The EventSourcedEntity class now has a property 'created_on', which replaces the attribute '_created_on'.
This change follows from the fact that the domain events no longer have an floating point attribute 'timestamp'
but instead a UUID attribute 'domain_event_id', which is set on an event sourced entity as '_initial_event_id'.
That UUID value is used to generate the floating point timestamp value of the 'created_on' property.

Please note, the mutator style has changed to use the `singledispatch` package. Mutators were implemented as a
big if-elif-else block. Subclasses of EventSourcedEntity must implement a static method called _mutator() in
order to have their own mutator function invoked when mutate() is called.

There is a new method called _apply() on EventSourcedEntity, which makes operations that need to apply events
have a suitably named method to call. The apply() method calls the mutate() class method, which is also used by the
event source repository to replay events. The mutate() class method calls the static method _mutator() with the
event and an initial state. So the static method _mutator is a good method to override in order to introduce
a mutator for the class.

Please see the Example class for details, and the documentation for singledispatch.

Also, for Cassandra users, the table name for stored events has changed to 'stored_events'. The column names
have changed to be single characters, for storage efficiency. Production data will need to be migrated.


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


## More Details About the Features

* Example application of event sourcing, with an example event sourced entity and example domain events, and with
 an example event sourced repository containing example entity instances, and an example entity factory method

* Storage-specific event sourced application classes

    * Base class for event sourced applications with SQLAlchemy

    * Base class for event sourced applications with Cassandra

    * Base class for event sourced applications with simple Python objects (non-persistent)

* Base class for event sourced applications, which provides an event store and a persistence subscriber, but
 which requires subclasses to implement a method that provides a stored event repository instance

* Example event sourced entity

* Base class for event sourced entities

    * Basic domain events, to model basic "created", "attribute changed", and "discarded" entity events

    * Mutator function, to apply a domain event to an entity, variously according to the type of the event

    * Event sourced property decorator, to help declare simple event sourced properties

    * A "discard" method which publishes the discarded event, to call when an entity is no longer wanted,

* Domain event base class, to model events in a domain

* In-process publish-subscribe mechanism, for in-process domain event propagation

* Persistence subscriber class, to subscribe to locally published domain events and append them to an event store

* Example event sourced domain entity repository

* Base class for event sourced domain entity repositories

* Event player, to recover a domain entity for a given domain entity ID, using an event store and a mutator

* Domain event store class

    * Method to append a new domain event

    * Method to get all the domain events for an entity

* Concrete stored event repository classes

    * Stored event repository to persist stored event objects in a relational database, using SQLAlchemy (as an ORM)

    * Stored event repository to persist stored events in Cassandra

    * Stored event repository using simple Python objects (non-persistent)

* Generic stored event class, to provide a form in which to persist domain events

* Function to get event topic from domain event class

* Function to resolve event topic into domain event class

* Function to serialize a domain event object to a stored event object

* Function to recreate a domain event object from a stored event object

* Base class for stored event repositories

    * Method to append a new stored event to the stored collection

    * Method to get all stored events for given entity ID

    * Method to get all stored events for given domain event topic

    * Method to get single domain event for given event ID

* Entity snapshots, to avoid replaying all events

* Method to get domain events for given entity ID, from given time

* Method to get domain events for given entity ID, until given time

* Method to get a limited number of domain events

* Generator that retrieves events in a succession of pages, emitting a
 continuous stream in ascending or descending order

* Time-bucketed logs, useful for accumulating an indefinite list of
 messages in an accessible manner

* Encrypted stored events, providing application level encryption

* Set-based collections

* Optimistic concurrency control

* Generalized suffix trees

Todo: Develop above to be an API reference.


## Forthcoming Features

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

* Linked pages of domain events ("Archived Log"), to allow event sourced projections easily to make sure they have
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

Todo: Develop above to be a release plan.


## Possible Future Backwards-Incompatible Changes

* Remove id_prefixes in stored entity ID, because it makes the code a
  bit complicated, since each domain event needs to know which entity
  class it is for, and that's not always desirable. This would involve
  internal code changes that probably wouldn't impact on applications
  using this package, however it would impact existing data. This
  change might not even be a good idea.

* Move base event classes off from abstract entity classes, so developers
  can't get confused with events defined on super classes that can't be
  retrieved from the event store, because they don't know which concrete
  class they pertain to, so can't be written with correct id prefixes.
  This would be a code change rather than a data migration thing. This
  wouldn't be an issue if we didn't use ID prefixes.

* Stored event repositories that primarily use version numbers instead
  of UUIDs to key and order stored events. This wouldn't be a backwards
  incompatible change, but an alternative transcoder and stored
  event repo.


## Project

This project is hosted on GitHub.

* https://github.com/johnbywater/eventsourcing


Questions, requests and any other issues can be registered here:

* https://github.com/johnbywater/eventsourcing/issues
