# Event sourcing in Python

[![Build Status](https://secure.travis-ci.org/johnbywater/eventsourcing.png)](https://travis-ci.org/johnbywater/eventsourcing)

## Install

Use pip to install the latest release from Python Package Index:

    pip install eventsourcing


## Development

The project is hosted on GitHub:

    https://github.com/johnbywater/eventsourcing


## Motivation and Inspiration

Event sourcing is really useful, but there is no event sourcing package in Python.

Although you can implement this stuff new for each project, there are common codes which can be reused.

Other packages on PyPI such as rewind and event-store don't really provide a library for event sourcing.

Inspiration:

* Martin Fowler's article on event sourcing http://martinfowler.com/eaaDev/EventSourcing.html

* Robert Smallshire's example code on Bitbucket https://bitbucket.org/sixty-north/d5-kanban-python/src

* Greg Young's articles (various) and EventStore code https://geteventstore.com/
 

## Features

* Domain event object class

* Function to get the event topic from a domain event class

* Function to resolve an event topic into a domain event class

* Function to serialize a domain event to a stored event

* Function to recreate a domain event from a stored event

* Stored event object class

* Abstract base class for stored event repository

* Method to get of all domain events for given domain entity ID

* Method to get all domain events for given domain event topic

* Method to get single domain event for given event ID

* Method to delete of all domain events for given domain entity ID (forthcoming)

* In-memory stored event repository, using simple Python objects

* SQLAlchemy stored event repository, with ORM model for stored events

* Cassandra stored event repository, with Cassandra column family for stored events (forthcoming)

* Event store class, to append domain events to a stored event repository

* Publish-subscribe mechanism, for in-process domain event propagation

* Persistence subscriber class, to receive published domain events and append them to an event store

* Abstract base class for event-sourced entities

* Event player, to return a recreated domain entity for a given domain entity mutator and entity ID

* Abstract base class for event-sourced repositories

* Snapshots of entity state at specific version, to avoid replaying all events (forthcoming)

* Retrieval of all events for given entity ID, from given version of the entity (forthcoming)

* Update stored event (domain model migration) (forthcoming)

* Application object class to hold the persistence subscriber, event sourced repositories, entity factory method

* Examples

## Usage

Start by defining a domain entity, and give it some domain events. There must
be a "created" event that is passed into the __init__ method of the entity.

In the example below, an Example entity has an ExampleCreated and an
ExampleDiscarded event. The Example.__init__ method accepts ExampleCreated events.

Todo: Inline the example entity.

Define a mutator that can change the state of the entity according to the domain events. The mutator
must handle all of the events. The mutator will at least handle the "created" event by instantiating
an entity object.

In the example below, the mutator can handle both the ExampleCreated and the ExampleDiscarded events.

Todo: Inline the example mutator.

Next, define a factory for the entity, that instantiates the "created" event, calls
the mutator, publishes the event, and returns the entity.

In the example below, the factory method is a module level function which firstly instantiates the
ExampleCreated event. The mutator is invoked, which returns an entity instance. The event is published,
in case there are any subscribers. Finally, the entity is returned to the caller of the factory method.

Todo: Inline the example factory method.

Next, define an event sourced repository class for your entity.

Inherit from the base class 'EventSourcedRepository' and define a get_mutator() method on the subclass.

Todo: Inline the example event sourced repo.

Finally, define an application to hold event sourced repo and the factory method, and to setup the
persistence subscriber, the event store, and a stored event persistence model.

Todo: Inline the example application.

Congratulations! You have create an event sourced application. Try using it by calling the factory
method to get a new entity, using the entity to discover the new entity ID, and using the discovered
entity ID to retrieve the entity from the event sourced repository.

Todo: Inline the example application test block.