# Event Sourcing in Python

[![Build Status](https://secure.travis-ci.org/johnbywater/eventsourcing.png?branch=develop)]
(https://travis-ci.org/johnbywater/eventsourcing)

A library for event sourcing in Python.


## Features

**Worked Examples** · A simple worked example application, with example entity, event sourced
repository, and factory method (see below). Included is a slightly more
sophisticated version of the example application below. Also, in the
'eventsourcing.contrib' package, there is a persistent "generalized
suffix tree" which shows how a more complex model could be written.

**Abstract Base Classes and Test Cases** · Make it simple to develop new applications, with custom entities, repositories,
domain events, and subscribers (see example below, and test suite cases).

**Optimistic Concurrency Control** · Implemented using atomic database system features. For example, with
Cassandra this accomplishes linearly-scalable distributed optimistic
concurrency control, guaranteeing application-level consistency of each
event stream, across a distributed application, without locking. Of
course, it is also possible to serialize the execution of commands
on an aggregate, to implement pesimistic concurrency control, but that
is out of the scope of this package. If you wish to do that, perhaps
something like [Zookeeper](https://zookeeper.apache.org/) might help.

**Application Level Encryption** · Symmetric encryption of all stored events, including snapshots and
logged messages, using a customizable cipher. Can optionally be applied
to particular events, or all stored events, or not applied at all
(the default). Included is an AES cipher, in CBC mode with 128 bit
blocksize, that uses a 16 byte encryption key passed in at run time,
and which generates a unique 16 byte initialization vector for each
encryption. Data is compressed before it is encrypted, which can mean
application performance is improved when encryption is enabled.

**Generic Event Store** · With an extendable set of adapters called "stored event repositories"
for popular ORMs and databases systems (e.g. Cassandra, SQLAlchemy).
Also supports using Python objects in memory, for rapid application
development. If your database system isn't supported, it will be easy
to adapt by writing a custom stored event repository. The event store
is also derived from an abstract base class in case you want to
use a custom event store in your application. There are test cases you
can use to make sure your implementations have the capabilities required
by the other parts of the application.

**Snapshots** · Avoids replaying an entire event stream to obtain the current state of
an entity, hence entity access time complexity becomes *O(1)* with
respect to the total number of events *N* in the stream, rather than *O(N)*.

**Fast Forwarding** · Of entities to latest published event - used with snapshots and also
when optimistic currency control exceptions are encountered.

**Customizable Transcoding** · Between domain events and stored events - allows customization of
database schemas when developing a custom stored event repositoriy.

**Collections** · An object-oriented alternative to "joins" - used for modelling
multiplicities of different kinds.

**Time-Bucketed Logs** · Logged messages, and log readers - for writing and reading an
indefinitely long stream of events in a scalable manner.


## Install

Use pip to install the [latest distribution](https://pypi.python.org/pypi/eventsourcing) from
the Python Package Index.

    pip install eventsourcing

If you want to run the test suite, or try the example below, then please install with the 
optional extra called 'test'.

    pip install eventsourcing[test]

After installing with the 'test' optional extra, the test suite should pass.

    python -m unittest discover eventsourcing.tests -v

Please register any issues you find.

* https://github.com/johnbywater/eventsourcing/issues


There is also a mailing list.

* https://groups.google.com/forum/#!forum/eventsourcing-users


## Usage

Start by defining a domain entity as a subclass of class 'EventSourcedEntity' (in module
'eventsourcing.domain.model.entity'). The domain events can be defined on the domain entity
class. The entity's constructor will accept the values needed to initialize
its variables.

In the example below, an 'Example' entity inherits 'Created', 'AttributeChanged', and 'Discarded'
events from its super class 'EventSourcedEntity'. It also inherits a mutator method that handles
those events. The Example entity has a constructor which takes two positional arguments ('a' and 'b')
and keyword arguments ('kwargs') which it passes directly to the base class constructor.
The 'mutableproperty' decorator is used to define mutable event sourced properties for entity attributes 'a'
and 'b'. The decorator introduces a setter that generates 'AttributeChanged' events when values are assigned
to the attributes. The entity inherits a discard() method, which generates the 'Discarded' event when called.
The 'Created' event is generated in a factory method (see below) and carries values used to initialise an entity.

```python
from eventsourcing.domain.model.entity import EventSourcedEntity, mutableproperty


class Example(EventSourcedEntity):

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

Next, define a factory method that returns new entity instances. Rather than directly constructing the entity object
instance, it should firstly instantiate a "created" domain event, and then call the mutator to obtain
an entity object instance. The factory method then publishes the event (for example, so that it might be
saved into the event store by the persistence subscriber) and returns the entity to the caller.

In the example below, the factory method is a module level function which firstly instantiates the
'Created' domain event. The Example's mutator is invoked with the Created event, which returns an
Example entity instance. The Example class inherits a mutator that can handle the Created, AttributeChanged,
and Discarded events. (The mutator could have been extended to handle other events, but for simplicity there
aren't any events defined in this example that the default mutator can't handle.) Once the
Example entity has been instantiated by the mutator, the Created event is published, and the new domain entity
is returned to the caller of the factory method.

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


Now, define an event sourced repository class for your entity. Inherit from
eventsourcing.infrastructure.event_sourced_repo.EventSourcedRepository and set the
'domain_class' attribute on the subclass.

In the example below, the ExampleRepository sets the Example class as its domain entity class.

```python
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository    

class ExampleRepository(EventSourcedRepository):

    domain_class = Example
```


Finally, define an application to have an event sourced repo and a factory method. Inheriting from
eventsourcing.application.main.EventSourcingApplication provides a persistence subscriber, an event store,
and stored event persistence when the application is instantiated. For convenience when using SQLAlchemy and
Cassandra to store events, two sub-classes are provided: EventSourcingWithSQLAlchemy and EventSourcingWithCassandra.

In the example below, the ExampleApplication has an ExampleRepository, and for convenience the
'register_new_example' factory method described above (a module level function) is used to implement a
synonymous method on the application class. It extends EventSourcingWithSQLAlchemy. It passes a 'db_uri'
argument, which is used to make the database connection.

It also passes a True value for 'enable_occ' so that optimistic concurrency control 
is enabled. If you aren't developing a distributed (or otherwise multi-threaded) application, you
don't need to use the optimistic concurrency control feature.

```python
from eventsourcing.application.with_sqlalchemy import EventSourcingWithSQLAlchemy

class ExampleApplication(EventSourcingWithSQLAlchemy):

    def __init__(self, db_uri):
        super(ExampleApplication, self).__init__(
            db_uri=db_uri,
            enable_occ=True,
        )
        self.example_repo = ExampleRepository(
            event_store=self.event_store,
        )

    def register_new_example(self, a, b):
        return register_new_example(a=a, b=b)
```

For simplicity, this application has just one type of entity. A real application may involve several different
types of entity, factory methods, entity repositories, and event sourced projections.

As shown below, an event sourced application object can be used as a context manager, which closes the application
at the end of the block. With an instance of the example application, call the factory method register_new_entity()
to register a new entity. Then, update an attribute value by assigning a value. Use the generated entity ID to subsequently
retrieve the registered entity from the repository. Check the changed attribute value has been stored. Discard
the entity and see that the repository gives a key error when an attempt is made to get the entity after it
has been discarded:

```python
with ExampleApplication(db_uri='sqlite:///:memory:') as app:
    
    # Register a new example.
    example1 = app.register_new_example(a=1, b=2)
    
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

If you want to model other domain events, then simply declare them on
the entity class like the events above, and implement methods on the
entity which instantiate those domain events, apply them to the entity,
publish to subscribers. Add mutator functions to apply the domain
events to the entity objects, for example by directly changing the
internal state of the entity.

The example above uses an SQLite in memory relational database, but you could change 'db_uri' to another
connection string if you have a real database. Here are some example connection strings - for
an SQLite file, for a PostgreSQL database, and for a MySQL database. See SQLAlchemy's create_engine()
documentation for details.

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
for formalisms for well-documented categories of of algorithms. Expose the capabilities of the framework
with an INTENTION-REVEALING INTERFACE. Now the other elements of the domain can focus on expressing the problem
("what"), delegating the intricacies of the solution ("how") to the framework."_

The list of features above, and the example of usage below, present the 'interface' and hopefully the 'intentions'. 
The 'intricacies' of the library mechanisms can be found in the source code.

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
