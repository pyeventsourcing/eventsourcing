.. eventsourcing documentation master file, created by
   sphinx-quickstart on Wed Apr 12 16:45:44 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

========================
Event Sourcing in Python
========================

A library for event sourcing in Python.

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

This documentation provides instructions for installing the package, highlights the main features of
the library, includes a detailed example of usage, describes the design of the software, and has
some background information about the project.

Please register questions, requests and any other `issues on GitHub
<https://github.com/johnbywater/eventsourcing/issues>`__.


.. toctree::
   :maxdepth: 2
   :caption: Contents

   topics/quick_start
   topics/installing
   topics/features
   topics/user_guide/index
   topics/design
   topics/background
   topics/release_notes


Reference
=========

..  * :ref:`genindex`
..  * :ref:`modindex`

* :ref:`search`

.. .. toctree::
..    :maxdepth: 1

..    ref/modules
