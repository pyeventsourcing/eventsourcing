# Event sourcing in Python

[![Build Status](https://secure.travis-ci.org/johnbywater/eventsourcing.png)](https://travis-ci.org/johnbywater/eventsourcing)


## Install

Use pip to install the latest release from Python Package Index. For the example below, and to make the tests work, please also install sqlalchemy (which isn't required if events are persisted in Cassandra - forthcoming).

    pip install eventsourcing[sqlalchemy]

After installation, the tests should pass.

    python -m unittest discover eventsourcingtests -v

## Development

The project is hosted on GitHub.

* https://github.com/johnbywater/eventsourcing


## Motivation and Inspiration

Event sourcing is really useful, but there is no event sourcing package in Python.

Although you can implement this stuff new for each project, there are common codes which can be reused.

Other packages on PyPI such as rewind and event-store don't really provide a library for event sourcing.

Inspiration:

* Martin Fowler's article on event sourcing
    * http://martinfowler.com/eaaDev/EventSourcing.html

* Robert Smallshire's example code on Bitbucket
    * https://bitbucket.org/sixty-north/d5-kanban-python/src

* Greg Young's articles (various) and EventStore code
     * https://geteventstore.com/


## Features

* Base class for domain events

* Base class for event-sourced domain entities

* Base class for event-sourced domain repositories

* Function to get the event topic from a domain event class

* Function to resolve an event topic into a domain event class

* Function to serialize a domain event to a stored event

* Function to recreate a domain event from a stored event

* Immutable stored event type

* Entity snapshots at specific version, to avoid replaying all events (forthcoming)

* Abstract base class for stored event repository

    * Method to get all domain events for given entity ID

    * Method to get all domain events for given domain event topic

    * Method to get single domain event for given event ID

    * Method to get all domain events for given entity ID, from given version of the entity (forthcoming)

    * Method to delete of all domain events for given domain entity ID (forthcoming)

* In-memory stored event repository, using simple Python objects for stored events

* SQLAlchemy stored event repository, using ORM to persist stored events in any supported database

* Cassandra stored event repository, using a column family to persist stored events in Cassandra (forthcoming)

* Event store class, to append domain events to a stored event repository

* Persistence subscriber class, to receive published domain events and append them to an event store

* Publish-subscribe mechanism, for in-process domain event propagation

* Event player, to return a recreated domain entity for a given domain entity mutator and entity ID

* Update stored event (domain model migration) (forthcoming)

* Application class to hold a persistence subscriber, an event sourced repositories, and entity factory methods

* Examples

* Subscriber that publishes domain events to RabbitMQ (forthcoming)

* Subscriber that publishes domain events to Amazon SQS (forthcoming)

* Republisher that subscribes to RabbitMQ and publishes domain events locally (forthcoming)

* Republisher that subscribers to Amazon SQS and publishes domain event locally (forthcoming)

* Event sourced indexes

## Usage

Start by defining a domain entity. The entity's constructor
should accept the values it needs to initialize its variables.

In the example below, an Example entity inherits a Created and a
Discarded events from the EventSourcedEntity.

```python
from eventsourcing.domain.model.entity import EventSourcedEntity
from eventsourcing.domain.model.events import publish

class Example(EventSourcedEntity):
    
    def __init__(self, a, b, **kwargs):
        super().__init__(**kwargs)
        self.a = a
        self.b = b
```

Next, define a factory method that returns new entity instances. Rather than directly constructing the entity object
instance, it should firstly instantiate a "created" domain event, and then call the mutator to obtain
an entity object instance. The factory method then publishes the event (for example, so that it might be
saved into the event store by the persistence subscriber) and returns the entity to the caller.

In the example below, the factory method is a module level function which firstly instantiates the
Example's Created domain event. The Example mutator is invoked, which returns an entity object instance when given a
Created event. The event is published, and the new domain entity is returned to the caller of the factory method.

    import uuid

    def register_new_example(a, b):
        """
        Factory method for example entities.
        """
        entity_id = uuid.uuid4().hex
        event = Example.Created(entity_id=entity_id, a=a, b=b)
        entity = Example.mutator(self=Example, event=event)
        publish(event=event)
        return entity


Next, define an event sourced repository class for your entity. Inherit from the base class
'EventSourcedRepository' and set the 'domain_class' attribute on the subclass.
In the example below, the ExampleRepository sets the Example class as its domain class.

    from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository    
    
    class ExampleRepository(EventSourcedRepository):    
        domain_class = Example


Finally, define an application to have the event sourced repo and the factory method. Inheriting from
EventSourcedApplication means a persistence subscriber, an event store, and stored event persistence
will be set up when the application is instantiated.

In the example below, the ExampleApplication has an ExampleRepository, and for convenience the
'register_new_example' factory method described above (a module level function) is used to implement a
synonymous method on the application class.

    from eventsourcing.application.main import EventSourcedApplication

    class ExampleApplication(EventSourcedApplication):
    
        def __init__(self):
            super().__init__()
            self.example_repo = ExampleRepository(event_store=self.event_store)
    
        def register_new_example(self, a, b):
            return register_new_example(a=a, b=b)


The event sourced application can be used as a context manager. Call the application's factory object to
register a new entity. Use the new entity's ID to retrieve the registered entity from the repository.

    with ExampleApplication() as app:

        # Register a new example.
        new_entity = app.register_new_example(a=10, b=20)

        entity_id = new_entity.id

        # Get the entity from the repo.
        saved_entity = app.example_repo[entity_id]

        assert new_entity == saved_entity


Congratulations! You have created a new event sourced application!
