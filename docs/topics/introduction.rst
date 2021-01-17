============
Introduction
============

What is event sourcing?
=======================

What is event sourcing? One definition suggests the state of an
event-sourced application is determined by a sequence of events.
Another definition has event sourcing as a persistence mechanism
for domain driven design.

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
for event-sourced domain driven design appears as a conceptually cohesive
mechanism, and so can be "partitioned into a separate lightweight framework".


This library
============

This is a library for event sourcing in Python. At its core, this library
supports storing and retrieving sequences of items, such as the domain events
of event-sourced aggregates in a domain driven design. A variety of schemas
and technologies can be used for sequencing and storing events, and this
library supports several of these possibilities.

To demonstrate how storing and retrieving domain events can be used effectively
as a persistence mechanism in an event-sourced application, this library includes
base classes for event-sourced aggregates and applications.

It is possible to define an entire application, and indeed an entire distributed
system of event-sourced applications, independently of infrastructure. That means system
behaviours can be rapidly developed whilst running the entire system synchronously
in a single thread with a single in-memory database. And then, the system can be run
asynchronously on a cluster with durable databases, with the system effecting exactly
the same behaviour.


Design overview
===============

The design of the library follows "layered architecture" in that there
are distinct and separate layers for interfaces, application, domain and
infrastructure. It also follows the "onion" or "hexagonal" or "clean"
architecture, in that the domain layer has no dependencies on any other
layer. The application layer depends on the domain and infrastructure
layers, and the interface layer depends only on the application layer.


Register issues
===============

This project is `hosted on GitHub <https://github.com/johnbywater/eventsourcing>`__.
Please `register any issues, questions, and requests
<https://github.com/johnbywater/eventsourcing/issues>`__ you may have.
