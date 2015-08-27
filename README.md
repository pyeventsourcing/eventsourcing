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

* Domain event class

* Stored event class

* Function to get the event topic from a domain event

* Function to serialize a domain event to a stored event

* Function to recreate domain event from stored event

* Retrieval of all events for given entity ID

* Retrieval of all events for given event topic

* Retrieval of single event for given event ID

* Abstract base class for stored event repository, and implementations for SQLAlchemy and Cassandra

* ORM for stored event in SQLAlchemy

* Column family for stored event in Cassandra (forthcoming)

* Event store class, to append domain events to a stored event repository

* Persistence subscriber class, listens for domain events and writes to an event store

* Publish-subscribe mechanism, for in-process domain event propagation

* Event sourced entity class, has domain events and a mutator that applies domain events to update instance state

* Event player class, to reconstitute a domain entity by replaying all its domain events through a mutator

* Event sourced repository class, uses the event player for a particular domain entity class

* Delete all events for given entity ID (forthcoming)

* Snapshots of entity state at specific version (forthcoming)

* Optimised retrieval of all events for given entity ID, from given version of the entity (forthcoming)

* Update stored event (domain model migration) (forthcoming)
