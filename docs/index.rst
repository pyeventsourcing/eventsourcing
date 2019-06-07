========================
Event Sourcing in Python
========================

A library for event sourcing in Python.

Introduction
============

What is event sourcing? One definition suggests the state of an event-sourced application
is determined by a sequence of events. Another definition has event sourcing as a
persistence mechanism for domain driven design.

Because it is common for the state of a software application to be partitioned across
a set of aggregate objects in a domain model, this library provides infrastructure to
support persisting and projecting domain events of individual aggregates. It suggests
a style for coding aggregates with command methods which trigger new domain events,
and shows how to propagate and process the state of event-sourced applications in a
pipelined system.

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

This project is `hosted on GitHub <https://github.com/johnbywater/eventsourcing>`__.
Please `register any issues, questions, and requests
<https://github.com/johnbywater/eventsourcing/issues>`__ you may have.


.. toctree::
   :maxdepth: 2
   :caption: Contents

   topics/quick_start
   topics/features
   topics/design
   topics/installing
   topics/infrastructure
   topics/domainmodel
   topics/application
   topics/notifications
   topics/projections
   topics/process
   topics/snapshotting
   topics/deployment
   topics/minimal
   topics/background
   topics/release_notes
   ref/modules
