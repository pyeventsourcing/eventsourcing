============
Introduction
============

What is event sourcing?
=======================

What is event sourcing? One definition suggests the state of an
event-sourced application is determined by a sequence of events.
Another definition has event sourcing as a persistence mechanism
for domain driven design.

That's the basic story, at least. In practice, because a sequence of
stored events can be queried in only a limited number of ways, to obtain
the views of the state of an application that users need when making
command requests, several other design patterns are needed to develop
useful software. And several other design patterns are needed to ensure
reliability, maintainability, and scalability.


This library
============

This is a library for event sourcing in Python. At its core, this library
supports storing and retrieving sequences of items, such as the domain events
of event-sourced aggregates in a domain driven design. A variety of schemas
and technologies can be used for sequencing and storing events, and this
library supports several of these possibilities.

To demonstrate how storing and retrieving domain events can be used effectively
as a persistence mechanism in an event-sourced application, this library includes
base classes for event-sourced domain entities and applications of different kinds.
An domain model developed using these classes will not depend on infrastructure
("onion" archictecture). A style is suggested for event-sourced aggregates: to have
command methods which "trigger" domain events. Triggered domain events are used to
mutate the state of the aggregate, and then stored. The stored events of an aggregate
can be retrieved and used to obtain the current state of the aggregate. The stored
events of an application can also be propagated and used to project the state of
the application into the materialised views needed by users. Stored events can also
be processed further by other applications in the same system, and by other systems.

It is also possible to define an entire application, and indeed an entire distributed
system of event-sourced applications, independently of infrastructure. That means system
behaviours can be rapidly developed whilst running the entire system synchronously
in a single thread with a single in-memory database. And then, the system can be run
asynchronously on a cluster with durable databases, with the system effecting exactly
the same behaviour.


A cohesive mechanism
====================

Quoting from Eric Evans' book `Domain Driven Design
<https://en.wikipedia.org/wiki/Domain-driven_design>`__:

.. pull-quote::

    *"Partition a conceptually COHESIVE MECHANISM into a separate
    lightweight framework. Particularly watch for formalisms for
    well-documented categories of algorithms. Expose the capabilities of the
    framework with an INTENTION-REVEALING INTERFACE. Now the other elements
    of the domain can focus on expressing the problem ('what'), delegating
    the intricacies of the solution ('how') to the framework."*

Although the basic event sourcing patterns are quite simple, and
can be reproduced in code for each project, the persistence mechanism
for event sourced domain driven design appears as a conceptually cohesive
mechanism, and so can be "partitioned into a separate lightweight framework".

Whilst some advocate that event sourcing is such a simple thing that you
can easily roll-your-own event sourcing framework for each project, in practice
it turns out reaching understanding and satisfaction (reliability, scalability,
maintainability) is a considerably more complicated and costly undertaking than
is disclosed by the simple story that is often told.

This library documents the experience of event sourcing across a broad range
of projects. It also functions as an informative "jumping off" point for those
who want to create their own framework and "own" all their own code. And it is
also used by many as a stable and convenient library that can be used to rapidly
develop working software that will be used in production.


Register issues
===============

This project is `hosted on GitHub <https://github.com/johnbywater/eventsourcing>`__.
Please `register any issues, questions, and requests
<https://github.com/johnbywater/eventsourcing/issues>`__ you may have.
