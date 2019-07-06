domain.model
============

The domain layer contains a domain model, and optionally services that work across
different entities or aggregates.

The domain model package contains classes and functions that can help develop an
event sourced domain model.

.. contents:: :local:

events
------

Base classes for domain events of different kinds.

.. automodule:: eventsourcing.domain.model.events
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


entity
------

Base classes for domain model entities.

.. autoclass:: eventsourcing.domain.model.entity.DomainEntity
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.domain.model.entity
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __init__


.. automodule:: eventsourcing.domain.model.entity
    :members:
    :special-members:
    :show-inheritance:
    :undoc-members:


aggregate
---------

Base classes for aggregates in a domain driven design.

.. automodule:: eventsourcing.domain.model.aggregate
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


command
-------

Commands as aggregates.

.. automodule:: eventsourcing.domain.model.command
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


decorator
---------

Decorators useful in domain models based on the classes in this library.

.. automodule:: eventsourcing.domain.model.decorators
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


snapshot
--------

Snapshotting is implemented in the domain layer as an event.

.. automodule:: eventsourcing.domain.model.snapshot
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


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


collection
----------

Collections.

.. automodule:: eventsourcing.domain.model.collection
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


array
-----

A kind of collection, indexed by integer. Doesn't need to replay all events to exist.

.. automodule:: eventsourcing.domain.model.array
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
