
.. _Cargo shipping example:

Application 2 - Cargo shipping
==============================

This example follows the original Cargo Shipping example that
figures in the DDD book, as worked up into a running application
by the `DDD Sample <http://dddsample.sourceforge.net/>`_  project:

    *"One of the most requested aids to coming up to speed on DDD has been a running example
    application. Starting from a simple set of functions and a model based on the cargo example
    used in Eric Evans' book, we have built a running application with which to demonstrate a
    practical implementation of the building block patterns as well as illustrate the impact
    of aggregates and bounded contexts."*

The original example was not event-sourced and was coded in Java. The example below
is an event-sourced version of the original coded in Python.

Application
-----------

The application object ``BookingService`` allows new cargo to be booked, cargo details
to be presented, the destination of cargo to be changed, choices of possible routes
for cargo to be presented, a route to be assigned, and for cargo handling events
to be registered.

The ``Booking`` application defines and registers custom transcodings for the
custom value objects that are defined and used in the domain model.

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/application.py

Domain model
------------

The aggregate ``Cargo`` allows new cargo bookings to be made, the destination
of the cargo to be changed, a route to be assigned, and for handling events
to be registered. It is defined in the more verbose style, using explicit
definitions of aggregate events, an explicit "create" method (``new_booking()``),
and command methods that explicitly trigger events by calling ``trigger_event()``.
An aggregate projector function is implemented on the aggregate object using
``@simpledispatchmethod``, with an event-specific method registered to handle
each type of aggregate event.

Custom value objects such as ``Location`` and ``Itinerary``,  are defined as
part of the domain model, and used in the ``Cargo`` aggregate events and methods.
For the purpose of simplicity in this example, a fixed collection of routes between
locations are also defined, but in practice these would be editable and could be
also modelled as event-sourced aggregates.

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/domainmodel.py


Interface
---------

The interface object ``BookingService`` repeats the application methods, allowing
new cargo to be booked, cargo details to be presented, the destination of cargo to
be changed, choices of possible routes for cargo to be presented, a route to be
assigned, and for cargo handling events to be registered.

It allows clients (e.g. a test case, or Web interface) to deal with simple object
types that can be easily serialised and deserialised. It interacts with the
application using the custom value objects defined in the domain model. For
the purposes of testing, we need to simulate the user selecting a preferred
itinerary from a list, which we do by picking the first in the list of presented
options using the ``select_preferred_itinerary()`` function.

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/interface.py


Test case
---------

Following the sample project, the test case has two test methods.
One test shows an administrator booking a new cargo, viewing the current
state of the cargo, and changing the destination. The other test goes
further by assigning a route to a cargo booking, tracking the cargo
handling events as it is shipped around the world, recovering by
assigning a new route after the cargo was unloaded in the wrong place,
until finally the cargo is claimed at its correct destination.

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/test.py
