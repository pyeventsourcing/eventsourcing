
.. _Cargo shipping example:

Cargo shipping example
======================

This example follows the original Cargo Shipping example that
figures in the DDD book, as coded in the
`DDD Sample <http://dddsample.sourceforge.net/>`__  project:

    *"One of the most requested aids to coming up to speed on DDD has been a running example
    application. Starting from a simple set of functions and a model based on the cargo example
    used in Eric Evans' book, we have built a running application with which to demonstrate a
    practical implementation of the building block patterns as well as illustrate the impact
    of aggregates and bounded contexts."*

This example demonstrates the use of an interface object to convert
application-specific object types to simple object types that can
be easily serialised, an event-sourced application that deals in
terms of custom value objects, a domain model that uses custom
value objects that and has an aggregate projector defined on the
aggregate class without using the declarative syntax.


Test case
---------

To keep things simple, we can define a test case using Python's
``unittest`` module.

.. code:: python

    import unittest


.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/test.py
    :pyobject: TestBookingService

Interface
---------

The interface allows clients to deal with simple object types that can be easily
serialised and deserialised.

.. code:: python

    from datetime import datetime
    from typing import Dict, List, Optional, Tuple, Union


    NextExpectedActivityDetails = Optional[Tuple[str, ...]]

    CargoDetails = Dict[
        str, Optional[Union[str, bool, datetime, NextExpectedActivityDetails]]
    ]

    LegDetails = Dict[str, str]

    ItineraryDetails = Dict[str, Union[str, List[LegDetails]]]


The interface interacts with the application using custom types
of value object defined in the domain model.


.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/interface.py
    :pyobject: BookingService

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/interface.py
    :pyobject: select_preferred_itinerary


Application
-----------

The application deals with the domain model aggregates, and registers transcodings
for the custom value objects that are used in aggregate events.

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/application.py
    :pyobject: BookingApplication

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/application.py
    :pyobject: HandlingActivityAsName

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/application.py
    :pyobject: ItineraryAsDict

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/application.py
    :pyobject: LegAsDict

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/application.py
    :pyobject: LocationAsName

Domain model
------------

The domain model is defined in the more verbose style, using explicit definitions
of aggregate events, with command methods that trigger events. The aggregate
projector function is implemented on the aggregate object using the single
dispatch decorator with an event-specific method registered to handle each type
of aggregate event.

Custom value objects are defined in as part of the domain model, and used in
the aggregate event objects.

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/domainmodel.py
    :pyobject: Cargo

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/domainmodel.py
    :pyobject: HandlingActivity

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/domainmodel.py
    :pyobject: Itinerary

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/domainmodel.py
    :pyobject: Leg

.. literalinclude:: ../../../eventsourcing/examples/cargoshipping/domainmodel.py
    :pyobject: Location

Run tests
---------

We can now run the tests.

.. code:: python

    if __name__ == '__main__':
        unittest.main()

::

    .
    ----------------------------------------------------------------------
    Ran 2 tests in 0.009s

    OK
