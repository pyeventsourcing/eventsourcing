============
Introduction
============

This documentation:

- highlights the :doc:`design </topics/design>` and :doc:`features </topics/features>` of the library,
- has instructions for :doc:`installing </topics/installing>` the package,
- describes
  the :doc:`domain model layer </topics/domainmodel>`,
  the :doc:`infrastructure layer </topics/infrastructure>`,  and
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


This library
============

This is a library for event sourcing in Python. At its core, this library supports
storing and retrieving sequences of items, such as the domain events of aggregates
in a event-sourced domain driven design.

To demonstrate how its persistence mechanism can be used effectively,
this library documentation has examples of event-sourced applications
with event-sourced domain models. The library base classes used in these
examples can be conveniently used to create your own applications.
A style is suggested for writing event-sourced domain models, and
event-soured aggregates that have command methods which trigger domain events.

Using this library, it is also possible to define an entire distributed system of
event-sourced applications independently of infrastructure. That means system
behaviours can be rapidly developed whilst running the entire system synchronously
in a single thread with a single in-memory database, and then the system can be run
asynchronously on a cluster with durable databases, with the system performing exactly
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
mechanism, and so have been "partitioned into a separate lightweight framework".


Register issues
===============

This project is `hosted on GitHub <https://github.com/johnbywater/eventsourcing>`__.
Please `register any issues, questions, and requests
<https://github.com/johnbywater/eventsourcing/issues>`__ you may have.

