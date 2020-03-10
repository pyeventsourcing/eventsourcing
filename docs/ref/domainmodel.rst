domain.model
============

The domain model package contains classes and functions that can help develop an
event sourced domain model.

.. contents:: :local:

.. py:module:: eventsourcing.domain.model.events

events
------

Base classes for domain events of different kinds.

.. automodule:: eventsourcing.domain.model.events
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.domain.model.entity

entity
------

Base classes for domain model entities.

.. automodule:: eventsourcing.domain.model.entity
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __init__


.. py:module:: eventsourcing.domain.model.aggregate

aggregate
---------

Base classes for aggregates in a domain driven design.

.. automodule:: eventsourcing.domain.model.aggregate
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.domain.model.command

command
-------

Commands as aggregates.

.. automodule:: eventsourcing.domain.model.command
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.domain.model.decorator

decorators
----------

Decorators useful in domain models based on the classes in this library.

.. automodule:: eventsourcing.domain.model.decorators
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.domain.model.snapshot

snapshot
--------

Snapshotting is implemented in the domain layer as an event.

.. automodule:: eventsourcing.domain.model.snapshot
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.domain.model.versioning

versioning
----------

Support for upcasting the state of older version of domain events is
implemented in base class
:class:`~eventsourcing.domain.model.versioning.Upcastable`.

.. automodule:: eventsourcing.domain.model.versioning
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.domain.model.timebucketedlog



timebucketedlog
---------------

Time-bucketed logs allow a sequence of the items that is sequenced by timestamp to
be split across a number of different database partitions, which avoids one
partition becoming very large (and then unworkable).

.. automodule:: eventsourcing.domain.model.timebucketedlog
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.domain.model.collection

collection
----------

Collections.

.. automodule:: eventsourcing.domain.model.collection
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.domain.model.array

array
-----

A kind of collection, indexed by integer. Doesn't need to replay all events to exist.

.. automodule:: eventsourcing.domain.model.array
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
