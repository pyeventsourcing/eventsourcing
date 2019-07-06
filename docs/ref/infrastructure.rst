infrastructure
==============

The infrastructure layer adapts external devices in ways that are useful
for the application, such as the way an event store encapsulates a database.

.. contents:: :local:


base
----

Abstract base classes for the infrastructure layer.

.. automodule:: eventsourcing.infrastructure.base
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


eventstore
----------

The event store provides the application-level interface to the event sourcing
persistence mechanism.

.. automodule:: eventsourcing.infrastructure.eventstore
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


cassandra
---------

Classes for event sourcing with Apache Cassandra.

.. automodule:: eventsourcing.infrastructure.cassandra.datastore
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.cassandra.factory
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.cassandra.manager
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.cassandra.records
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


datastore
---------

Base classes for concrete datastore classes.

.. automodule:: eventsourcing.infrastructure.datastore
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


django
------

A Django application for event sourcing with the Django ORM.

.. automodule:: eventsourcing.infrastructure.django.factory
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.django.manager
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.django.models
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.django.utils
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


eventplayer
-----------

Base classes for event players of different kinds.

.. automodule:: eventsourcing.infrastructure.eventplayer
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


eventsourcedrepository
----------------------

Base classes for event sourced repositories (not abstract, can be used directly).

.. automodule:: eventsourcing.infrastructure.eventsourcedrepository
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


integersequencegenerators
-------------------------

Different ways of generating sequences of integers.

.. automodule:: eventsourcing.infrastructure.integersequencegenerators.base
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.integersequencegenerators.redisincr
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


iterators
---------

Different ways of getting sequenced items from a datastore.

.. automodule:: eventsourcing.infrastructure.iterators
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


repositories
------------

Repository base classes for entity classes defined in the library.

.. automodule:: eventsourcing.infrastructure.repositories.array
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.repositories.collection_repo
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.repositories.timebucketedlog_repo
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


sequenceditem
-------------

The persistence model for storing events.

.. automodule:: eventsourcing.infrastructure.sequenceditem
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


sequenceditemmapper
-------------------

The sequenced item mapper maps sequenced items to application-level objects.

.. automodule:: eventsourcing.infrastructure.sequenceditemmapper
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


snapshotting
------------

Snapshotting avoids having to replay an entire sequence of events to obtain
the current state of a projection.

.. automodule:: eventsourcing.infrastructure.snapshotting
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


sqlalchemy
----------

Classes for event sourcing with SQLAlchemy.

.. automodule:: eventsourcing.infrastructure.sqlalchemy.datastore
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.sqlalchemy.factory
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.sqlalchemy.manager
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.sqlalchemy.records
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


timebucketedlog_reader
----------------------

Reader for timebucketed logs.

.. automodule:: eventsourcing.infrastructure.timebucketedlog_reader
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
