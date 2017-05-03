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

This documentation provides instructions for :doc:`installing <topics/installing>` the
package, highlights the main :doc:`features <topics/features>` of the library, includes
detailed :doc:`examples of usage <topics/user_guide/index>`, describes the
:doc:`design <topics/design>` of the software, and has some :doc:`background <topics/background>`
information about the project.

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
   topics/user_guide/index
   topics/design
   topics/release_notes


Reference
=========

* :ref:`search`
* :ref:`genindex`
* :ref:`modindex`


Modules
=======

.. toctree::
   :maxdepth: 1

   ref/modules


