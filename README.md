# Event sourcing in Python

[![Build Status](https://secure.travis-ci.org/johnbywater/eventsourcing.png)](https://travis-ci.org/johnbywater/eventsourcing)

## Install

Use pip to install the latest release from Python Package Index (PyPI):

    pip install eventsourcing


## Development

The project is hosted on github:

    https://github.com/johnbywater/eventsourcing


## Motivation and Inspiration

Event sourcing is really useful, but there is no event sourcing package in Python.

Although you can implement this stuff new for each project, there are common codes which can be reused.

Other packages on PyPI such as rewind and event-store don't really provide a library for event sourcing.

Inspiration:

* Martin Fowler's article on event sourcing http://martinfowler.com/eaaDev/EventSourcing.html

* Greg Young's articles (various) and EventStore code https://geteventstore.com/
 
* Robert Smallshire's example code on Bitbucket https://bitbucket.org/sixty-north/d5-kanban-python/src


## Features

* Domain event object class

* Function to get the event topic from a domain event class

* Function to resolve an event topic into a domain event class

* Function to serialize a domain event to a stored event

* Function to recreate a domain event from a stored event

* Stored event object class

* Abstract base class for stored event repository

* Retrieval of all domain events for given domain entity ID

* Retrieval of all domain events for given domain event topic

* Retrieval of single domain event for given event ID

* Deletion of all domain events for given domain entity ID (forthcoming)

* In-memory (simple Python object based) stored event repository

* SQLAlchemy stored event repository

* SQLAlchemy ORM model for stored events

* Cassandra stored event repository (forthcoming)

* Cassandra column family for stored events (forthcoming)

* Event store class, to append domain events to a stored event repository

* Publish-subscribe mechanism, for in-process domain event propagation

* Persistence subscriber class, to receive published domain events and append them to an event store

* Abstract base class for event-sourced domain entities

* Event player, to return a recreated domain entity for a given domain entity mutator and entity ID

* Abstract base class for event-sourced repositories

* Snapshots of entity state at specific version, to avoid replaying all events (forthcoming)

* Optimised retrieval of all events for given entity ID, from given version of the entity (forthcoming)

* Update stored event (domain model migration) (forthcoming)

* Application object class to hold the persistence subscriber, event sourced repositories, entity factory method

* Examples
