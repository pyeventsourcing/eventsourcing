========================
Event Sourcing in Python
========================

A library for event sourcing in Python.

Overview
========

What is event sourcing? One definition suggests the state of an event sourced application
is determined by a sequence of events. Another definition has event sourcing as a
persistence mechanism for domain driven design. It is common for the state of a
software application to be modelled across a set of entities or aggregates.

Therefore, this library provides mechanisms for event sourced applications, a way for domain
events to be stored and replayed, and a style for coding entities with both state that is
driven by events and behaviour that drives events.

This documentation provides: instructions for :doc:`installing </topics/installing>` the package,
highlights the main :doc:`features </topics/features>` of the library,
describes the :doc:`design </topics/design>` of the software,
the :doc:`infrastructure layer </topics/infrastructure>`,
the :doc:`domain model layer </topics/domainmodel>`,
the :doc:`application layer </topics/application>`,
has information about :doc:`deployment </topics/deployment>`, and
has some :doc:`background </topics/background>` information about the project.

This project is `hosted on GitHub <https://github.com/johnbywater/eventsourcing>`__.
Please `register any issues, questions, and requests
<https://github.com/johnbywater/eventsourcing/issues>`__ on GitHub.


.. toctree::
   :maxdepth: 2
   :caption: Contents

   topics/background
   topics/quick_start
   topics/installing
   topics/features
   topics/design
   topics/infrastructure
   topics/domainmodel
   topics/application
   topics/snapshotting
   topics/minimal
   topics/notifications
   topics/deployment
   topics/release_notes
   ref/modules
