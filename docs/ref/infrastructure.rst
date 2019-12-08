infrastructure
==============

The infrastructure layer adapts external devices in ways that are useful
for the application, such as the way an event store encapsulates a database.

.. contents:: :local:


.. py:module:: eventsourcing.infrastructure.sequenceditem

sequenceditem
-------------

The persistence model for storing events.

.. automodule:: eventsourcing.infrastructure.sequenceditem
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.infrastructure.sequenceditemmapper

sequenceditemmapper
-------------------

The sequenced item mapper maps sequenced items to application-level objects.

.. automodule:: eventsourcing.infrastructure.sequenceditemmapper
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.infrastructure.base

base
----

Abstract base classes for the infrastructure layer.

.. automodule:: eventsourcing.infrastructure.base
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__



.. py:module:: eventsourcing.infrastructure.datastore

datastore
---------

Base classes for concrete datastore classes.

.. automodule:: eventsourcing.infrastructure.datastore
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.infrastructure.cassandra

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


.. py:module:: eventsourcing.infrastructure.django

django
------

Infrastructure for event sourcing with the Django ORM. This package functions
as a Django application. It can be included in "INSTALLED_APPS" in settings.py
in your Django project. There is just one migration, to create tables that do
not exist.

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


.. py:module:: eventsourcing.infrastructure.sqlalchemy

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


.. py:module:: eventsourcing.infrastructure.popo

popo
----

Infrastructure for event sourcing with "plain old Python objects".

.. automodule:: eventsourcing.infrastructure.popo.factory
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.popo.manager
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.popo.mapper
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__

.. automodule:: eventsourcing.infrastructure.popo.records
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.infrastructure.eventstore

eventstore
----------

The event store provides the interface to the event sourcing
persistence mechanism that is used by applications.

.. automodule:: eventsourcing.infrastructure.eventstore
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.infrastructure.eventsourcedrepository

eventsourcedrepository
----------------------

Base classes for event sourced repositories (not abstract, can be used directly).

.. automodule:: eventsourcing.infrastructure.eventsourcedrepository
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.infrastructure.iterators

iterators
---------

Different ways of getting sequenced items from a datastore.

.. automodule:: eventsourcing.infrastructure.iterators
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.infrastructure.factory

factory
-------

Infrastructure factory.


.. automodule:: eventsourcing.infrastructure.factory
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.infrastructure.snapshotting

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


.. py:module:: eventsourcing.infrastructure.timebucketedlog_reader

timebucketedlog_reader
----------------------

Reader for timebucketed logs.


.. automodule:: eventsourcing.infrastructure.timebucketedlog_reader
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__


.. py:module:: eventsourcing.infrastructure.repositories

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


.. py:module:: eventsourcing.infrastructure.integersequencegenerators

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


