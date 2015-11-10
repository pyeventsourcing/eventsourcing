# Event sourcing in Python

[![Build Status](https://secure.travis-ci.org/johnbywater/eventsourcing.png)](https://travis-ci.org/johnbywater/eventsourcing)

A library for event sourcing in Python.


## Install

Use pip to install the [latest distribution](https://pypi.python.org/pypi/eventsourcing) from
the Python Package Index. So the test suite might pass, and so the usage example
below will work, install with the optional extra called 'test'.

    pip install eventsourcing[test]


After installation, the test suite should pass.

    python -m unittest discover eventsourcingtests -v


Please register an issue if you find a bug.


## Development

The project is hosted on GitHub.

* https://github.com/johnbywater/eventsourcing


Issues can be registered here:

* https://github.com/johnbywater/eventsourcing/issues


## Motivation and Inspiration

Although the event sourcing patterns are each quite simple, and they can be reproduced in code for each project,
they do suggest cohesive mechanisms, for example applying and publishing the events generated within domain
entities, storing and retrieving selections of the events in a highly scalable manner, replaying the stored
events for a particular entity to obtain the current state, and projecting views of the event stream that are
persisted in other models. Quoting from the "Cohesive Mechanism" pages in Eric Evan's Domain Driven Design book:

_"Therefore: Partition a conceptually COHESIVE MECHANISM into a separate lightweight framework. Particularly watch
for formalisms for well-documented categories of of algorithms. Expose the capabilities of the framework
with an INTENTION-REVEALING INTERFACE. Now the other elements of the domain can focus on expressing the problem
("what"), delegating the intricacies of the solution ("how") to the framework."_

The list of features below, and the examples beneath, present the 'interface' and hopefully the 'intentions'. 
The 'intricacies' of the library mechanisms can be found in the source code.

Inspiration:

* Martin Fowler's article on event sourcing
    * http://martinfowler.com/eaaDev/EventSourcing.html

* Greg Young's discussions about event sourcing, and EventStore system
    * https://dl.dropboxusercontent.com/u/9162958/CQRS/Events%20as%20a%20Storage%20Mechanism%20CQRS.pdf
    * https://geteventstore.com/ (Java)

* Robert Smallshire's brilliant example code on Bitbucket
    * https://bitbucket.org/sixty-north/d5-kanban-python/src


## Features

* Domain event base class, to model events in a domain

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

* Concrete stored event repository classes

    * Stored event repository to persist stored event objects in a relational database, using SQLAlchemy (as an ORM) 

    * Stored event repository to persist stored events in Cassandra

    * Stored event repository using simple Python objects (non-persistent)

* Domain event store class

    * Method to append a new domain event
    
    * Method to get all the domain events for an entity

* In-process publish-subscribe mechanism, for in-process domain event propagation to subscriber objects

* Persistence subscriber class, to subscribe to locally published domain events and append them to an event store

* Base class for event sourced entities

    * Basic domain events, to model basic "created", "attribute changed", and "discarded" entity events

    * Basic "mutator" function, to apply the basic domain events to any domain entity

    * Event sourced property decorator, to help declare simple event sourced properties

    * A "discard" method which publishes the discarded event, to call when an entity is no longer wanted, 

* Event player, to recover a domain entity for a given domain entity ID, using an event store and a mutator

* Base class for event sourced domain entity repositories, to recover domain entities using an event player

* Abstract base class for event sourced applications, having an event store and a persistence subscriber, but requiring a stored event repository

* Concrete event sourced application classes

    * Base class for event sourced applications with SQLAlchemy, which provides a stored event repository that uses SQLAlchemy

    * Base class for event sourced applications with Cassandra, which provides a stored event repository that uses Cassandra

* Example application of event sourcing, with an example event sourced entity and example domain events, and with an example event sourced repository containing example entity instances, and an example entity factory method

### Forthcoming features

* Stored event repository to persist stored events in a file using a very simple file format

* Stored event repository to persist stored events using MongoDB

* Stored event repository to persist stored events using HBase

* Method to get all domain events for given entity ID, from given version of the entity (forthcoming)

* Method to get all domain events for given entity ID, until given time (forthcoming)

* Method to delete all domain events for given domain entity ID (forthcoming)

* Method to get all domain events in the order they occurred (forthcoming)

* Storage retries and fallback strategies, to protect against failing to write an event (forthcoming)

* Subscriber that publishes domain events to RabbitMQ (forthcoming)

* Subscriber that publishes domain events to Amazon SQS (forthcoming)

* Republisher that subscribes to RabbitMQ and publishes domain events locally (forthcoming)

* Republisher that subscribers to Amazon SQS and publishes domain event locally (forthcoming)

* Linked pages of domain events ("Archived Log"), to allow event sourced projections easily to make sure they have all the events (forthcoming)

* Base class for event sourced projections or views (forthcoming)

    * In memory event sourced projection, which needs to replay entire event stream when system starts up (forthcoming)

    * Persistent event sourced projection, which stored its projected state, but needs to replay entire event stream when initialized  (forthcoming)

* Event sourced indexes, as persisted event source projections, to discover extant entity IDs (forthcoming)

* Entity snapshots, to avoid replaying all events (forthcoming)

* Event pointer, to refer to an event in a stream (forthcoming)

* Updating stored events, to support domain model migration (forthcoming)

* Something to store serialized event attribute values separately from the other event information, to prevent large attribute values inhibiting performance and stability - different sizes could be stored in different ways... (forthcoming)

* Different kinds of stored event
    * IDs generated from content, e.g. like Git (forthcoming)
    * cryptographically signed stored events (forthcoming)
    * encrypted stored events (forthcoming)
    
* Branch and merge mechanism for domain events (forthcoming)

* Support for asynchronous I/O, with an application that uses an event loop (forthcoming)

* More examples (forthcoming)

* Great documentation! (forthcoming)


## Usage

Start by defining a domain entity as a subclass of class 'EventSourcedEntity' (in module
'eventsourcing.domain.model.entity'). The domain events can be defined on the domain entity
class. The entity's constructor will accept the values needed to initialize
its variables.

In the example below, an 'Example' entity inherits 'Created', 'AttributeChanged', and 'Discarded'
events from its super class 'EventSourcedEntity'. It also inherits a mutator method that handles
those events. The Example entity has a constructor which takes two positional arguments ('a' and 'b')
and keyword arguments ('kwargs') which it passes directly to the base class constructor.
The 'eventsourcedproperty' decorator is used to define event sourced properties for entity attributes 'a'
and 'b'. The decorator introduces a setter that generates 'AttributeChanged' events when values are assigned
to the attributes. The entity inherits a discard() method, which generates the 'Discarded' event when called.
The 'Created' event is generated in a factory method (see below) and carries values used to initialise an entity.

```python
from eventsourcing.domain.model.entity import EventSourcedEntity, eventsourcedproperty


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

    @eventsourcedproperty
    def a(self):
        return self._a

    @eventsourcedproperty
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
    entity = Example.mutator(event=event)
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
synonymous method on the application class. It extends EventSourcingWithSQLAlchemy.

```python
from eventsourcing.application.with_sqlalchemy import EventSourcingWithSQLAlchemy

class ExampleApplication(EventSourcingWithSQLAlchemy):

    def __init__(self, db_uri):
        super(ExampleApplication, self).__init__(db_uri=db_uri)
        self.example_repo = ExampleRepository(event_store=self.event_store)

    def register_new_example(self, a, b):
        return register_new_example(a=a, b=b)
```

For simplicity, this application has just one type of entity. A real application may involve several different
types of entity, factory methods, entity repositories, and event sourced projections.

An event sourced application object can be used as a context manager, which helps close things down at the
end. With an application instance, call its factory method to register a new entity. Update an
attribute value. Use the generated entity ID to subsequently retrieve the registered entity from the
repository. Check the changed attribute value has been stored.

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

Congratulations! You have created a new event sourced application!

If you want to model other domain events, then simply declare them on the entity class like the events above,
and implement methods on the entity which instantiate those domain events, apply them to the entity, publish to
subscribers. Extend the EventSourcedEntity.mutator() method on the entity class, to apply the domain events to
entity objects for example by directly changing the internal state of the entity.

The example above uses an SQLite in memory relational database, but you could change 'db_uri' to another
connection string if you have a real database. Here are some example connection strings - for
an SQLite file, for a PostgreSQL database, and for a MySQL database. See SQLAlchemy's create_engine()
documentation for details.

```
sqlite:////tmp/mydatabase

postgresql://scott:tiger@localhost:5432/mydatabase

mysql://scott:tiger@hostname/dbname
```
