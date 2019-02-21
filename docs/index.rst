========================
Event Sourcing in Python
========================

A library for event sourcing in Python.

Overview
========

What is event sourcing? One definition suggests the state of an event-sourced application
is determined by a sequence of events. Another definition has event sourcing as a
persistence mechanism for domain driven design. Therefore, this library makes it easy to
define, publish, persist, retrieve, project, and propagate the domain events of a software
application.

It is common for the state of a software application to be distributed across a set of
entities or aggregates. Therefore, this library provides infrastructure to support
event sourcing the state of entities or aggregates in an application, and suggests a
style for coding an application with event-sourced domain model entities or aggregates
that have behaviour which triggers events.

This documentation provides: instructions for :doc:`installing </topics/installing>` the package,
highlights the main :doc:`features </topics/features>` of the library,
describes the :doc:`design </topics/design>` of the software,
the :doc:`infrastructure layer </topics/infrastructure>`,
the :doc:`domain model layer </topics/domainmodel>`,
the :doc:`application layer </topics/application>`,

shows how :doc:`notifications </topics/notifications>` and :doc:`projections </topics/projections>`
can be combined to make a :doc:`reliable distributed system </topics/process>`,
has information about :doc:`deployment </topics/deployment>`, and
has some :doc:`background </topics/background>` information about the project.

This project is `hosted on GitHub <https://github.com/johnbywater/eventsourcing>`__.
Please `register any issues, questions, and requests
<https://github.com/johnbywater/eventsourcing/issues>`__ on GitHub.


.. toctree::
   :maxdepth: 2
   :caption: Contents

   topics/release_notes
   topics/background
   topics/quick_start
   topics/installing
   topics/features
   topics/design
   topics/infrastructure
   topics/minimal
   topics/domainmodel
   topics/application
   topics/deployment
   topics/snapshotting
   topics/notifications
   topics/projections
   topics/process
   ref/modules
