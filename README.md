# Event Sourcing in Python

[![Build Status](https://secure.travis-ci.org/johnbywater/eventsourcing.png?branch=develop)]
(https://travis-ci.org/johnbywater/eventsourcing)
[![Coverage Status](https://coveralls.io/repos/github/johnbywater/eventsourcing/badge.svg?branch=develop)]
(https://coveralls.io/github/johnbywater/eventsourcing?branch=develop)
[![Gitter chat](https://badges.gitter.im/gitterHQ/services.png)]
(https://gitter.im/eventsourcing-in-python/eventsourcing)

A library for event sourcing in Python.

## Overview

The aim of this library is to make it easier to write event sourced applications
in Python. One definition of event sourcing suggests the state of an event sourced
application is determined by a sequence of events. It is common for an application
to be implemented using domain entities, with the application state distributed across
the entities.

Therefore, this library provides mechanisms useful in such an application: a style
for coding entity behaviours that mutate the state of the entity by instantiating
and applying and then publishing domain events of different kinds; and a way for
those events to be stored and replayed to obtain the state of an entity in the
application on demand.

This document highlights the main features of the library,
provides instructions for installing the package, describes the
design of the software, includes a detailed example of usage and
has some background information about the project.

With the major features complete, the current focus of development
work is towards: refactoring the code for greater clarity and greater
flexibility; a test suite with 100% line coverage; a much better
distinction between time-sequenced and integer-sequenced event streams;
support for storing events in a broader range database management
systems and services, and something called "boxes" (applications for bounded
contexts).

## Features

**Event Store** — Appends and retrieves domain events. The event store uses
a stored event repository to append and retrieve stored events. The event store uses a
transcoder to serialise and deserialise domain events as store events. The library has a
number of different stored event repositories that adapt a variety of ORMs and
databases systems (e.g. SQLAlchemy, Cassandra). If your database system isn't
already supported, it will be easy to adapt with a custom stored event repository.

**Event Players** — Use the event store to retrieve domain events. An event player
reconstitutes entities of a particular type from their domain events, optionally with
snapshotting. Snapshotting avoids replaying an entire event stream to obtain
the current state of an entity. A snapshot strategy is included which reuses
the capabilities of this library by implementing snapshots as domain events. It can
easily be substituted with a strategy that, for example, uses a dedicated table for snapshots.

**Persistence Subscriber** - Listens for published domain events, and
appends the domain events to the event store whenever a domain event is
published. Domain events are typically published by the methods of an entity.
The persistence subscriber is an example of an application policy ("do Y whenever X happens").

**Synchronous Publish-Subscribe Mechanism** — Stable and deterministic,
with handlers called in the order they are registered, and with which
calls to publish events do not return until all event subscribers have
returned. In general, subscribers are policies of the application, which may 
execute further commands whenever an particular kind of event is received.
Publishers of domain events are typically the methods of an entity.

**Customizable Transcoding** — Between domain events and stored events,
allows support to be added for serialization and deserialization of
custom value object types, and also makes it possible to use different
database schemas when developing a custom stored event repository.

**Application-Level Encryption** — Symmetric encryption of stored
events, including snapshots and logged messages, using a customizable
cipher. Can be used to encrypt some events, or all events, or not applied at
all (the default). Included is an AES cipher strategy, by default in CBC mode
with 128 bit blocksize, that uses a 16 byte encryption key passed in at run time,
and which generates a unique 16 byte initialization vector for each encryption.
In this cipher, data is compressed before it is encrypted, which can mean application
performance is surprisingly improved when encryption is enabled.

**Optimistic Concurrency Control** — Applicable to integer sequenced events only.
Can be used to ensure a distributed or horizontally scaled application doesn't
become inconsistent due to concurrent method execution. Leverages any optimistic
concurrency controls in the database adapted by the stored event repository. With
Cassandra, this can accomplish linearly-scalable distributed optimistic concurrency
control, guaranteeing sequential consistency of an event stream, across a distributed
application. It is also possible to serialize calls to the methods of an entity, but
that is currently out of the scope of this package - if you wish to do that, perhaps
something like [Zookeeper](https://zookeeper.apache.org/) might help.

**Worked Examples** — A simple worked example application (see below), with example
entity class, example event sourced repository, and example factory method.

**Abstract Base Classes** — For application objects, event soured domain entities,
domain entity repositories, domain events, transcoding strategies, snapshotting strategies,
stored event repositories, notification log views and readers, test cases, etc. These
classes are at least suggestive of how to structure an event sourced application, and
can be used directly to extend this library for your own purposes.

**Collections** — Event sourced collections, for modelling different
kinds of multiplicity.

**Time-Bucketed Logs** — Provide a way of writing a long
stream of events in a highly scalable manner. Includes log objects,
logged message events and a log reader implemented as a generator that
can span across many many buckets. For example, a domain event log
that allows all stored events in an application to be logged in
a linearly scalable manner, and then retrieved in order, limited by
number, from any point in time until another point in time, in reverse
or ascending order.

**Notification Logs** - Provide a way of reading a long
sequence of events in a highly scalable manner. Includes a notification
logger that writes an event sourced log that can be indexed with a
contiguous integer sequence, and a log reader implemented as a generator
that selects a part of a sequence using Python's list slice syntax.
Support is included in the library for presenting notification logs
as RESTful HTTP services with an HTTP client reading the logs, in the
dynamic manner described by Vaughn Vernon in his book *Implementing Domain Driven Design*.

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


## Install

Use pip to install the [latest distribution](https://pypi.python.org/pypi/eventsourcing) from
the Python Package Index.

    pip install eventsourcing

If you want to use SQLAlchemy, then please install with the optional extra called 'sqlalchemy'.

    pip install eventsourcing[sqlalchemy]

Similarly, if you want to use Cassandra, then please install with the optional extra called 'cassandra'.

    pip install eventsourcing[cassandra]

If you want to run the test suite, or try the example below with different backends, then
please install with the optional extra called 'test'.

    pip install eventsourcing[test]

After installing with the 'test' optional extra, the test suite should
pass.

    python -m unittest discover eventsourcing.tests -v

Please register any issues you find.

* https://github.com/johnbywater/eventsourcing/issues


There is also a mailing list.

* https://groups.google.com/forum/#!forum/eventsourcing-users


And a room on Gitter.

* https://gitter.im/eventsourcing-in-python/eventsourcing


## Design

The design of the library follows the layered architecture: interfaces, application, domain, and infrastructure.

The domain layer contains a model of the supported domain, and services that depend on that
model. The infrastructure layer encapsulates the infrastructural services required by the application.

The application is responsible for binding domain and infrastructure, and has policies
such as the persistence subscriber, which stores domain events whenever they are published by the model.

The example application has an example respository, from which example entities can be retrieved. It
also has a factory method to register new example entities. Each repository has an event player, which share
an event store with the persistence subscriber. The persistence subscriber uses the event store
to store domain events, and the event players use the event store to retrieve the stored events. The event
players also share with the model the mutator functions that are used to apply domain events to an initial state.

Functionality such as transcoding and snapshotting is factored as strategy objects, injected into dependents
by constructor parameter. Application level encryption is a transcoding option.

The stored event repository layer allows domain events to be stored in a range of database 
services, and can optionally make use of any optimistic concurrency controls the database
system may provide.


![UML Class Diagram](https://www.lucidchart.com/publicSegments/view/9919fa7f-2c6d-4aac-b189-5f2871a69aee/image.png)


## Usage

Start by opening a new Python file in your favourite editor, or start
a new project in your favourite IDE. To create a working program, you
can either type or copy and paste the following code snippets into a
single Python file. Feel free to experiment by making variations. If
you installed the library into a Python virtualenv, please check that
your virtualenv is activated before running your program.

#### Step 1: define a class of event sourced entity

Write yourself a new event sourced entity class. The entity is responsible
for publishing domain events. As a rule, the state of the entity will be
determinted by the events that have been published by its methods.

```python
from eventsourcing.domain.model.entity import EventSourcedEntity


class Example(EventSourcedEntity):
    """An example of an event sourced entity class."""
```

The entity class domain events can be defined on the domain entity
class. In the example below, an 'Example' entity defines 'Created',
'AttributeChanged', and 'Discarded' events.

Add those events to your entity class.


```python
class Example(EventSourcedEntity):
    """An example of an event sourced entity class."""

    class Created(EventSourcedEntity.Created):
        pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged):
        pass

    class Discarded(EventSourcedEntity.Discarded):
        pass
```

When are these events published? The 'Created' event can be published by
a factory method (see below). The 'Created' event attribute values are used
to construct an entity. The 'AttributeChanged' event can by published by a
method of the entity. The 'Discarded' event is published by the discard()
method.

For convenience, the '@attribute' decorator can be used with
 Python properties to define mutable event sourced, event publishing attributes.
(The decorator introduces a "setter" that generates an 'AttributeChanged'
event when a value is assigned, and a "getter" that presents the current
attribute value.)

Add the two mutable attributes 'a' and 'b' to your entity class,
and adjust the import statement to import 'attribute'.

```python
from eventsourcing.domain.model.entity import EventSourcedEntity, attribute

class Example(EventSourcedEntity):
    """An example of an event sourced entity class."""

    class Created(EventSourcedEntity.Created):
        pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged):
        pass

    class Discarded(EventSourcedEntity.Discarded):
        pass

    @attribute
    def a(self):
        """This is attribute 'a'."""

    @attribute
    def b(self):
        """This is attribute 'b'."""
```

That's everything to publish domain events. How are they
applied to the entity?

The entity class inherits a mutator method that will handle
those events. For example, when a 'Created' event is handled by the
mutator, the attribute values of the Created event object are used to
call the entity class constructor. And when an 'AttributeChanged' event
is handled by the mutator, the new value is assigned to a private
attribute exposed by the mutable property.

Add the constructor to your entity class. It takes two positional
arguments 'a' and 'b', and '**kwargs' so other keyword arguments
will be passed through to the base class constructor.


```python
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

    @attribute
    def a(self):
        """This is attribute 'a'."""

    @attribute
    def b(self):
        """This is attribute 'b'."""
```

Please note, this Example class can be instantiated without
any infrastructure - it isn't already coupled to a database.
It can function entirely as a standalone class, for example
its attribute values can be changed. If it had methods, you
could call them.

The attribute values can be changed by assigning values. Unfortunately, since there isn't a database, the attribute
values will not somehow persist once the instance has gone out of scope.

Because it is an entity, it does need an ID. The entity ID is not
mutable attribute and cannot be changed e.g. by assignment.

```python
example = Example(a=1, b=2, entity_id='entity1')

assert example.a == 1
assert example.b == 2
assert example.id == 'entity1'

example.a = 12
example.b = 23

assert example.a == 12
assert example.b == 23

try:
    example.id = 'entity2'
except AttributeError:
    pass
else:
    raise AssertionError
```

If you want to model other domain events, then simply declare them on
the entity class like the events above, and implement methods on the
entity which instantiate those domain events, apply them to the entity,
publish to subscribers. Add mutator functions to apply the domain
events to the entity objects, for example by directly changing the
internal state of the entity. See the beat_heart() method on the
extended version of this example application, included in this library.

Todo: Include the beat_heart() method in this section.

#### Step 2: define an entity factory method

Next, define a factory method that can be used to create new entities. Rather
than directly constructing the entity object instance and "saving" it, the
factory method firstly creates a unique entity ID, it instantiates a 'Created'
domain event with the initial entity attribute values, and then calls the entity
class mutator to obtain an entity object. The factory method then publishes the
domain event so that, for example, it might be saved into an event store by a
persistence subscriber (see below). The factory method finishes by returning
the new entity it has created to its caller.

```python
from eventsourcing.domain.model.events import publish
import uuid

def register_new_example(a, b):
    # Create an entity ID.
    entity_id = uuid.uuid4().hex
    
    # Instantiate a domain event.
    event = Example.Created(entity_id=entity_id, a=a, b=b)
    
    # Mutate with the created event to construct the entity.
    entity = Example.mutate(event=event)
    
    # Publish the domain event.
    publish(event=event)
    
    # Return the new entity.
    return entity
```

Now try using the factory method to create an example entity.

```python
example = register_new_example(a=1, b=2)

assert example.a == 1
assert example.b == 2

example.a = 12
example.b = 23

assert example.a == 12
assert example.b == 23

assert example.id
```

How can entities created this way become persistent? And how will existing
stored entities be obtained? Entities are retrieved from repositories.


#### Step 3: define an event sourced repository

The next step is to define an event sourced repository class for your
entity. Inherit from 'EventSourcedRepository'. Set the 'domain_class'
attribute to be your Example entity class.

```python
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository

class ExampleRepository(EventSourcedRepository):

    domain_class = Example

```

When the repository is instantiated, it will construct an event
player. The entity class mutator is passed to the event player
as a constructor parameter, so that the event player can know
how to replay domain events when reconstituting an entity for
the repository.


#### Step 4: define an event sourced application

The final step is to make yourself an application object. Application objects
are used to bind domain and infrastructure. This involves having a stored event
repository that adapts the database system you want to use.

The stored event repository is used by the event store. The event store is
also used by the persistence subscriber to store domain events, and by
domain entity repositories to retrieve the events of a requested entity.

Add an application class, inheriting from 'EventSourcedApplication',
that has an example event sourced repo. The super class constructs a
persistence subscriber and an event store, but the methods can be overridden
if you wish to supply your own variations of those objects.

```python
from eventsourcing.application.base import EventSourcedApplication

class ExampleApplication(EventSourcedApplication):

    def __init__(self, **kwargs):
        super(ExampleApplication, self).__init__(**kwargs)
        
        # Example repo.
        self.example_repo = ExampleRepository(
            event_store=self.event_store,
        )
```

For simplicity, this example application has just one entity repository.
A more fully developed application may have many repositories, several
factory methods, other application services, various event sourced
projections, and a range of policies in addition to the persistence
subscriber.


#### Step 5: setup datastore and stored event repository

When constructing the application object, you will need to pass in
a stored event repository. Because many variations of datastores and
schemas are possible, the dependencies have been made fully explicit.

In this example, we use an in-memory SQLite database, a stored event repository
that works with SQLAlchemy, and an SQLAlchemy model for stored events.

```python
from eventsourcing.infrastructure.datastore.sqlalchemyorm import SQLAlchemySettings, SQLAlchemyDatastore
from eventsourcing.infrastructure.storedevents.sqlalchemyrepo import SQLAlchemyStoredEventRepository
from eventsourcing.infrastructure.storedevents.sqlalchemyrepo import SqlStoredEvent

settings = SQLAlchemySettings(
    uri='sqlite:///:memory:',
)
        
datastore = SQLAlchemyDatastore(
        settings=settings,
        tables=(SqlStoredEvent,),
)

datastore.setup_connection()
datastore.setup_tables()

stored_event_repository = SQLAlchemyStoredEventRepository(
    datastore=datastore,
    stored_event_table=SqlStoredEvent,
    always_check_expected_version=True,
    always_write_entity_version=True,
)
```

Take care in locating the calls to setup the tables and connect
to the database. The appropriate solution in your context will
depend on your model of execution. Normally you want to setup
the connection once per process, and setup the tables once only.
But in a test suite (and sometimes in migration scripts, especially
if your migration scripts somehow unfortunately interact with your
test suite) you may need to do such things more than once.

The example above uses an SQLite in memory relational database, but you
could change 'uri' to any valid connection string. Here are some example
connection strings: for an SQLite file; for a PostgreSQL database; and
for a MySQL database. See SQLAlchemy's create_engine() documentation for details.

```
sqlite:////tmp/mydatabase

postgresql://scott:tiger@localhost:5432/mydatabase

mysql://scott:tiger@hostname/dbname
```

Similarly to the support for storing events in SQLAlchemy, there
are object classes in the library for Cassandra. Support for other
databases is forthcoming.

Please note, neither database connection nor schema setup is the
responsibility of the application object. All these components can
easily be substituted for others you may craft, and perhaps should be.


#### Step 6: run the application

As shown below, an event sourced application object can be used as a
context manager, which closes the application at the end of the block,
closing the persistence subscriber and unsubscribing its event handlers.

With an instance of the example application, call the factory method
register_new_entity() to register a new entity.

You can update an attribute of the entity by assigning a new value. This
time, the application's persistence subscriber will store the attribute
changed event. You can now use the entity ID to retrieve the registered
entity from the repository. You will see the new attribute value persists
across instantiations of the entity.

Finally, discard the entity. Observe that the repository's dictionary like
interface raises a Python key error whenever an attempt is made to get an entity
that has been discarded.


```python
with ExampleApplication(stored_event_repository=stored_event_repository) as app:

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

Congratulations! You have created yourself an event sourced application.

Take care in locating calls to open and close your application. Normally
you want only one instance of the application running in any
given process, otherwise duplicate persistence subscribers will attempt
to store duplicate events, resulting in sad faces.

Todo: Something code that presents the generated events that are now in
the stored event repository created in step 5.


#### Step 7 (optional): enable application-level encryption

To enable application-level encryption, you can set the application keyword
argument 'always_encrypt' to a True value, and also pass in a cipher. With
application level encryption, application data will be encrypted at rest and
in transit, which can help prevent data loss.

```python
from eventsourcing.domain.services.cipher import AESCipher

def construct_application():
    return ExampleApplication(
        stored_event_repository=stored_event_repository,
        cipher=AESCipher(aes_key='0123456789abcdef'),
    )

with construct_application() as app:
    # Register a new example.
    example1 = register_new_example(a='secret data', b='more secrets')
```

Todo: Step 8 (optional): enable optimistic concurrency control


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


## Upgrade Notes

### Upgrading From 1.0.x to 1.1.x

You don't need to do anything. However before using the new optimistic concurrency controls
you will need to migrate an existing database schema to have the new 'entity_versions' table,
and you will also need to add a record to that table for each stored event. See notes in doc
string of EventSourcedApplication class for a zero-downtime migration approach.

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


## Project

This project is hosted on GitHub.

* https://github.com/johnbywater/eventsourcing


Questions, requests and any other issues can be registered here:

* https://github.com/johnbywater/eventsourcing/issues
