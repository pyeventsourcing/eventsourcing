============
Introduction
============

This documentation:

- highlights the :doc:`design of the library </topics/design>` and :doc:`core features </topics/features>`,
- has instructions for :doc:`installing </topics/installing>` the package,
- describes the :doc:`infrastructure layer </topics/infrastructure>`,
  the :doc:`domain model layer </topics/domainmodel>`, and
  the :doc:`application layer </topics/application>`,
- shows how :doc:`notifications </topics/notifications>` and
  :doc:`projections </topics/projections>` can be combined
  to make a :doc:`reliable distributed system </topics/process>`,
- has information about :doc:`deployment </topics/deployment>`, and
- has some :doc:`background </topics/background>` information about the project.


What is event sourcing?
=======================

What is event sourcing? One definition suggests the state of an
event-sourced application is determined by a sequence of events.
Another definition has event sourcing as a persistence mechanism
for domain driven design.


Cohesive mechanism
==================

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
mechanism, and so it can be "partitioned into a separate lightweight framework".


This library
============

At its core, this library supports storing and retrieving sequences of items,
such as domain events for aggregates in a domain driven design. A sequence of
stored events can be used to obtain the current state of an aggregate.

To demonstrate how the persistence mechanism can be used effectively,
this library also shows how to create simple event-sourced applications. A
style is suggested for writing stand-alone domain models, with aggregates that
have command methods that trigger domain events that are used to mutate
the state of the aggregate. An application has a repository, and notification
log that can be used to propagate the state of the application as a single
sequence of event notifications.

Using this library, it is also possible to define an entire distributed
system of event-sourced applications independently of infrastructure. System
behaviours can be rapidly developed and easily maintained whilst running the
entire system synchronously in a single thread with a single in-memory database,
and then the system can be run asynchronously on a cluster with durable databases,
with the system performing exactly the same behaviour.

Register issues
===============

This project is `hosted on GitHub <https://github.com/johnbywater/eventsourcing>`__.
Please `register any issues, questions, and requests
<https://github.com/johnbywater/eventsourcing/issues>`__ you may have.
