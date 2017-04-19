.. eventsourcing documentation master file, created by
   sphinx-quickstart on Wed Apr 12 16:45:44 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

========================
Event Sourcing in Python
========================

A library for event sourcing in Python.

.. toctree::
   :maxdepth: 2

   topics/installing
   topics/user_guide/index
   topics/design
   topics/wsgi

.. toctree::
   :maxdepth: 1
   :caption: Reference:

   ref/modules


Overview
========

What is event sourcing? One definition suggests the state of an event sourced application
is determined by a sequence of events. Another definition has event sourcing as a
persistence mechanism for domain driven design. In any case, it is common for the state
of a software application to be distributed or partitioned across a set of entities or aggregates
in a domain model.

Therefore, this library provides mechanisms useful in event sourced applications: a style
for coding entity behaviours that emit events; and a way for the events of an
entity to be stored and replayed to obtain the entities on demand.

Documentation provides instructions for installing the package, highlights the main features of
the library, includes a detailed example of usage, describes the design of the software, and has
some background information about the project.

Features
========

**Event store** — appends and retrieves domain events. The event store uses a
"sequenced item mapper" and an "active record strategy" to map domain events
to a database in ways that can be easily substituted.

**Persistence policy** — subscribes to receive published domain events.
Appends received domain events to an event store whenever a domain event is
published. Domain events are typically published by the methods of an entity.

**Event player** — reconstitutes entities by replaying events, optionally with
snapshotting. An event player is used by an entity repository to determine the
state of an entity. The event player retrieves domain events from the event store.

**Sequenced item mapper** — maps between domain events and "sequenced items", the archetype
persistence model used by the library to store domain events. The library supports two
different kinds of sequenced item: items that are sequenced by an increasing series
of integers; and items that are sequenced in time. They support two different kinds of
domain events: events of versioned entities (e.g. an aggregate in domain driven design),
and unversioned timestamped events (e.g. entries in a log).

**Active record strategy** — maps between "sequenced items" and database records (ORM).
Support can be added for a new database schema by introducing a new active record strategy.

**Application-level encryption** — encrypts and decrypts stored events, using a cipher
strategy passed as an option to the sequenced item mapper. Can be used to encrypt some
events, or all events, or not applied at all (the default). Included is a cipher strategy
which uses a standard AES cipher, by default in CBC mode with 128 bit blocksize and a 16
byte encryption key, and which generates a unique 16 byte initialization vector for each
encryption. In this cipher strategy, data is compressed before it is encrypted, which can
mean application performance is improved when encryption is enabled.

**Optimistic concurrency control** — can be used to ensure a distributed or
horizontally scaled application doesn't become inconsistent due to concurrent
method execution. Leverages any optimistic concurrency controls in the database
adapted by the stored event repository. For example the Cassandra database, which implements
the Paxos protocol, can accomplish linearly-scalable distributed optimistic concurrency
control, guaranteeing sequential consistency of the events of an entity, across concurent
application threads. It is also possible to serialize calls to the methods of an
entity, but that is out of the scope of this package — if you wish to do that,
perhaps something like [Zookeeper](https://zookeeper.apache.org/) might help.

**Snapshotting** — avoids replaying an entire event stream to
obtain the state of an entity. A snapshot strategy is included which reuses
the capabilities of this library by implementing snapshots as time-sequenced domain
events. It can easily be substituted with one that uses a dedicated table for snapshots.

**Abstract base classes** — suggest how to structure an event sourced application.
The library has base classes for application objects, domain entities, entity repositories,
domain events of various types, mapping strategies, snapshotting strategies, cipher strategies,
test cases, etc. They are well factored, relatively simple, and can be easily extended for your own
purposes. If you wanted to create a domain model that is entirely stand-alone (recommended by
purists for maximum longevity), you might start by copying the library classes.

**Synchronous publish-subscribe mechanism** — propagates events from publishers to subscribers.
Stable and deterministic, with handlers called in the order they are registered, and with which
calls to publish events do not return until all event subscribers have returned. In general,
subscribers are policies of the application, which may execute further commands whenever a
particular kind of event is received. Publishers of domain events are typically methods of domain entities.

**Worked examples** — a simple worked example application (see below) with an example
entity class, with example domain events, an example factory method, an example mutator function,
and an example database table.


Background
==========

Although the event sourcing patterns are each quite simple, and they can
be reproduced in code for each project, they do suggest cohesive
mechanisms, for example applying and publishing the events generated
within domain entities, storing and retrieving selections of the events
in a highly scalable manner, replaying the stored events for a
particular entity to obtain the current state, and projecting views of
the event stream that are persisted in other models. Quoting from the
"Cohesive Mechanism" pages in Eric Evan's Domain Driven Design book:

*"Therefore: Partition a conceptually COHESIVE MECHANISM into a separate
lightweight framework. Particularly watch for formalisms for
well-documented categories of algorithms. Expose the capabilities of the
framework with an INTENTION-REVEALING INTERFACE. Now the other elements
of the domain can focus on expressing the problem ("what"), delegating
the intricacies of the solution ("how") to the framework."*

The example usage (see above) introduces the "interface". The
"intricacies" can be found in the source code.

Inspiration:

-  Martin Fowler's article on event sourcing

   -  http://martinfowler.com/eaaDev/EventSourcing.html

-  Greg Young's discussions about event sourcing, and EventStore system

   -  https://www.youtube.com/watch?v=JHGkaShoyNs
   -  https://www.youtube.com/watch?v=LDW0QWie21s
   -  https://dl.dropboxusercontent.com/u/9162958/CQRS/Events%20as%20a%20Storage%20Mechanism%20CQRS.pdf
   -  https://geteventstore.com/

-  Robert Smallshire's brilliant example code on Bitbucket

   -  https://bitbucket.org/sixty-north/d5-kanban-python/src

-  Various professional projects that called for this approach, across
   which I didn't want to rewrite the same things each time

See also:

-  'Evaluation of using NoSQL databases in an event sourcing system' by
   Johan Rothsberg

   -  http://www.diva-portal.se/smash/get/diva2:877307/FULLTEXT01.pdf

-  Wikipedia page on Object-relational impedance mismatch

   -  https://en.wikipedia.org/wiki/Object-relational\_impedance\_mismatch

Upgrade notes
=============

**Upgrading from 1.x to 2.x**

Version 2 departs from version 1 by using sequenced items as the
persistence model (was stored events in version 1). This makes version 2
incompatible with version 1. However, with a little bit of code it would
be possible to rewrite all existing stored events from version 1 into
the version 2 sequenced items, since the attribute values are broadly
the same. If you need help with this, please get in touch.


Project
=======

This project is hosted on GitHub.

-  https://github.com/johnbywater/eventsourcing

Questions, requests and any other issues can be registered here:

-  https://github.com/johnbywater/eventsourcing/issues


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
