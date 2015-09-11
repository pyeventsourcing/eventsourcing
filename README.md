# Event sourcing in Python

[![Build Status](https://secure.travis-ci.org/johnbywater/eventsourcing.png)](https://travis-ci.org/johnbywater/eventsourcing)

A library for event sourcing in Python.


## Install

Use pip to install the [latest distribution](https://pypi.python.org/pypi/eventsourcing) from
the Python Package Index.

For the examples below, and so that the test suite might pass, please also install the 'sqlalchemy'
distribution.

    pip install eventsourcing sqlalchemy


After installation, if you run the test suite, it should pass.

    python -m unittest discover eventsourcingtests -v


Please register an issue if you find a bug.


## Development

The project is hosted on GitHub.

* https://github.com/johnbywater/eventsourcing


Issues can be registered here:

* https://github.com/johnbywater/eventsourcing/issues


## Motivation and Inspiration

Event sourcing is really fantastic, but there doesn't appear to be a general library for event sourcing in Python.
This can present a dilemma at the start of a project: whether or not to delay so that the basics can be put in
place. The 'rewind' package is coded to work with ZeroMQ. The 'event-store' looks to be along the right lines,
but provides a particular event store rather than broader range of elements of event sourcing which can be easily
extended and optionally combined to make event sourced applications that support their domain.

Although the event sourcing patterns are each quite simple, and they can be reproduced in code for each project,
they do suggest cohesive mechanisms, for example applying and publishing the events generated within domain
entities, storing and retrieving selections of the events in a highly scalable manner, replaying the stored
events for a particular entity to obtain the current state, and projecting views of the event stream that are
persisted in other models. Quoting from the "Cohesive Mechanism" pages in Eric Evan's Domain Driven Design book:

_"Therefore: Partition a conceptually COHESIVE MECHANISM into a separate lightweight framework. Particularly watch
for formalisms for well-documented categories of of algorithms. Expose the capabilities of the framework
with an INTENTION-REVEALING INTERFACE. Now the other elements of the domain can focus on expressing the problem
("what"), delegating the intricacies of the solution ("how") to the framework."_

The list of features below, and the examples beneath, present the 'interfaces' and hopefully the intentions
for this library. The intricacies of the library mechanisms can be found in the library source code.

Inspiration:

* Martin Fowler's article on event sourcing
    * http://martinfowler.com/eaaDev/EventSourcing.html

* Robert Smallshire's example code on Bitbucket
    * https://bitbucket.org/sixty-north/d5-kanban-python/src

* Greg Young's discussions about event sourcing, and EventStore system
    * https://dl.dropboxusercontent.com/u/9162958/CQRS/Events%20as%20a%20Storage%20Mechanism%20CQRS.pdf
    * https://geteventstore.com/


## Features

* Base class for immutable domain events

* Generic immutable stored event type

* Function to get event topic from domain event class

* Function to resolve event topic into domain event class

* Function to serialize domain events to stored event objects

* Function to recreate domain events from stored event objects

* Base class for stored event repositories

    * Method to get all domain events in the order they occurred (forthcoming)

    * Method to get all domain events for given entity ID, in the order they occurred

    * Method to get all domain events for given domain event topic

    * Method to get single domain event for given event ID

    * Method to get all domain events for given entity ID, from given version of the entity (forthcoming)
    
    * Method to get all domain events for given entity ID, until given time (forthcoming)

    * Method to delete all domain events for given domain entity ID (forthcoming)

* Concrete stored event repository implementations for common database management systems (SQL and NoSQL)

    * Simple stored event repository, using simple Python objects for stored events (non-persistent)
    
    * SQLAlchemy stored event repository, using ORM to persist stored events in any supported database
    
    * Cassandra stored event repository, using a column family to persist stored events in Cassandra (forthcoming)
    
* Persistence subscriber class, to listen for published domain events and append them to its event store

* Event store class, to convert domain events to stored events appended to its stored event repository

    * Storage retries and fallback strategies, to protect against failing to write an event

* In-process publish-subscribe mechanism, for in-process domain event propagation to subscriber objects

* Base class for event sourced entities

* Base class for event sourced repositories

* Event player, to return a recreated domain entity for a given domain entity mutator and entity ID

* Update stored event (domain model migration) (forthcoming)

* Base class for event sourced applications

* Base event sourced application class, to have a stored event repository, an event store, a persistence subscriber, domain specific event sourced repositories and entity factory methods

* Subscriber that publishes domain events to RabbitMQ (forthcoming)

* Subscriber that publishes domain events to Amazon SQS (forthcoming)

* Republisher that subscribes to RabbitMQ and publishes domain events locally (forthcoming)

* Republisher that subscribers to Amazon SQS and publishes domain event locally (forthcoming)

* Event sourced indexes, as persisted event source projections, to discover extant entity IDs (forthcoming)

* Base class for event sourced projections or views (forthcoming)

    * In memory event sourced projection, which needs to replay entire event stream when system starts up
    
    * Persistent event sourced projection, which stored its projected state, but needs to replay entire event stream when initialized

* Ability to clear and rebuild a persisted event sourced projection (such as an index), by republishing
all events from the event store, with it as the only subscriber (forthcoming)

* Entity snapshots, to avoid replaying all events (forthcoming)

* Stream pointer, to refer to an event in a stream (forthcoming)

* Something to store serialized event attribute values separately from the other event information, to prevent large attribute values inhibiting performance and stability - different sizes could be stored in different ways...

* Different kinds of stored event
    * IDs generated from content like Git
    * cryptographically signed
    * encrypted
    
* Branch and merge mechanism for domain events

* Examples (see below, more examples are forthcoming)

* Great documentation! (forthcoming)


## Usage

Start by defining a domain entity. The entity's constructor
should accept the values it needs to initialize its variables.

In the example below, an Example entity inherits Created, Discarded,
and AttributeChanged events from its super class EventSourcedEntity.

```python
from eventsourcing.domain.model.entity import EventSourcedEntity, eventsourcedproperty


class Example(EventSourcedEntity):
    """
    Example event sourced application.

    This application has an Example repository, and a factory method for
    registering new examples. It inherits an event store, a persistence
    subscriber, and a stored event repository, and a database connection.
    """

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
Example Created domain event. The Example class's mutator is invoked with the Created event, which returns an
Example entity instance. The Example class inherits a mutator that can handle the Created, AttributeChanged,
and Discarded events. The mutator could have been extended (or replaced) on the Example class, to handle other events,
but for simplicity there aren't any events defined in this example that the default mutator can't handle. Once the
Example entity has been instantiated, the Created event is published, and the new domain entity is returned to the
caller of the factory method.

```python
from eventsourcing.domain.model.events import publish
import uuid

def register_new_example(a, b):
    """
    Factory method for Example entities.
    """
    entity_id = uuid.uuid4().hex
    event = Example.Created(entity_id=entity_id, a=a, b=b)
    entity = Example.mutator(entity=Example, event=event)
    publish(event=event)
    return entity

```

Next, define an event sourced repository class for your entity. Inherit from the base class
'EventSourcedRepository' and set the 'domain_class' attribute on the subclass.
In the example below, the ExampleRepository sets the Example class as its domain class.

```python
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository    

class ExampleRepository(EventSourcedRepository):
    """
    An example event sourced repository, provides access to Example event sourced entities.
    """
    domain_class = Example

```

Finally, define an application to have the event sourced repo and the factory method. Inheriting from
EventSourcedApplication sets up a persistence subscriber, an event store, and stored event persistence
when the application is instantiated.

In the example below, the ExampleApplication has an ExampleRepository, and for convenience the
'register_new_example' factory method described above (a module level function) is used to implement a
synonymous method on the application class.

```python
from eventsourcing.application.main import EventSourcedApplication

class ExampleApplication(EventSourcedApplication):
    """
    An example event sourced application.

    This application has an Example repository, and a factory method for
    registering new "examples". It inherits a persistence subscriber, an
    event store, a stored event repository, and a database connection.
    """
    def __init__(self, db_uri):
        """
        Args:
            db_uri: Database connection string for stored event repository.
        """
        super(ExampleApplication, self).__init__(db_uri=db_uri)
        self.example_repo = ExampleRepository(event_store=self.event_store)

    def register_new_example(self, a, b):
        return register_new_example(a=a, b=b)

```


The example uses an SQLite in memory relational database, but you could change 'db_uri' to another
connection string if you have a real database. Here are some example connection strings - for
an SQLite file, for a PostgreSQL database, and for a MySQL database. See SQLAlchemy's create_engine()
documentation for details.

```
sqlite:////tmp/mydatabase

postgresql://scott:tiger@localhost:5432/mydatabase

mysql://scott:tiger@hostname/dbname
```


The event sourced application can be used as a context manager, which helps close things down at the
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
