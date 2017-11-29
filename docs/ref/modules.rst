===========
Module docs
===========

This document describes the packages, modules, classes, functions and other code
details of the library.

* :ref:`genindex`
* :ref:`modindex`

.. contents:: :local:


-------------
eventsourcing
-------------

The eventsourcing package contains packages for the application layer, the domain
layer, the infrastructure layer, and the interface layer. There is also a module
for exceptions, an example package, and a utils module.

application
===========

The application layer brings together the domain and infrastructure layers.

base
----

.. automodule:: eventsourcing.application.base
    :members:
    :show-inheritance:
    :undoc-members:


policies
--------

.. automodule:: eventsourcing.application.policies
    :members:
    :show-inheritance:
    :undoc-members:


simple
------

.. automodule:: eventsourcing.application.simple
    :members:
    :show-inheritance:
    :undoc-members:


domain
======

The domain layer contains a domain model, and optionally services that work across
different aggregates.

model
-----

The domain model package contains classes and functions that can help develop an
event sourced domain model.

.. automodule:: eventsourcing.domain.model.aggregate
    :members:
    :show-inheritance:
    :undoc-members:


array
~~~~~

A kind of collection, indexed by integer. Doesn't need to replay all events to exist.

.. automodule:: eventsourcing.domain.model.array
    :members:
    :show-inheritance:
    :undoc-members:


collection
~~~~~~~~~~

Decorators useful in domain models based on the classes in this library.

.. automodule:: eventsourcing.domain.model.decorators
    :members:
    :show-inheritance:
    :undoc-members:


entity
~~~~~~

Base classes for domain entities of different kinds.

.. automodule:: eventsourcing.domain.model.entity
    :members:
    :show-inheritance:
    :undoc-members:


events
~~~~~~

Base classes for domain events of different kinds.

.. automodule:: eventsourcing.domain.model.events
    :members:
    :show-inheritance:
    :undoc-members:


snapshot
~~~~~~~~

Snapshotting is implemented in the domain layer as an event.

.. automodule:: eventsourcing.domain.model.snapshot
    :members:
    :show-inheritance:
    :undoc-members:


timebucketedlog
~~~~~~~~~~~~~~~

Time-bucketed logs allow a sequence of the items that is sequenced by timestamp to
be split across a number of different database partitions, which avoids one
partition becoming very large (and then unworkable).

.. automodule:: eventsourcing.domain.model.timebucketedlog
    :members:
    :show-inheritance:
    :undoc-members:


infrastructure
==============

The infrastructure layer adapts external devices in ways that are useful
for the application, such as the way an event store encapsulates a database.

activerecord
------------

Abstract base class for active record strategies.

.. automodule:: eventsourcing.infrastructure.activerecord
    :members:
    :show-inheritance:
    :undoc-members:

cassandra
---------

Classes for event sourcing with Apache Cassandra.

.. automodule:: eventsourcing.infrastructure.cassandra.datastore
    :members:
    :show-inheritance:
    :undoc-members:

.. automodule:: eventsourcing.infrastructure.cassandra.activerecords
    :members:
    :show-inheritance:
    :undoc-members:


cipher
------

Classes for application-level encryption.

.. automodule:: eventsourcing.infrastructure.cipher.base
    :members:
    :show-inheritance:
    :undoc-members:


.. automodule:: eventsourcing.infrastructure.cipher.aes
    :members:
    :show-inheritance:
    :undoc-members:


datastore
---------

Base classes for concrete datastore classes.

.. automodule:: eventsourcing.infrastructure.datastore
    :members:
    :show-inheritance:
    :undoc-members:


eventplayer
-----------

Base classes for event players of different kinds.

.. automodule:: eventsourcing.infrastructure.eventplayer
    :members:
    :show-inheritance:
    :undoc-members:


eventsourcedrepository
----------------------

Base classes for event sourced repositories (not abstract, can be used directly).

.. automodule:: eventsourcing.infrastructure.eventsourcedrepository
    :members:
    :show-inheritance:
    :undoc-members:


eventstore
----------

The event store provides the application-level interface to the event sourcing
persistence mechanism.

.. automodule:: eventsourcing.infrastructure.eventstore
    :members:
    :show-inheritance:
    :undoc-members:


integersequencegenerators
-------------------------

Different ways of generating sequences of integers.

.. automodule:: eventsourcing.infrastructure.integersequencegenerators.base
    :members:
    :show-inheritance:
    :undoc-members:

.. automodule:: eventsourcing.infrastructure.integersequencegenerators.redisincr
    :members:
    :show-inheritance:
    :undoc-members:


iterators
---------

Different ways of getting sequenced items from a datastore.

.. automodule:: eventsourcing.infrastructure.iterators
    :members:
    :show-inheritance:
    :undoc-members:


repositories
------------

Repository base classes for entity classes defined in the library.

.. automodule:: eventsourcing.infrastructure.repositories.array
    :members:
    :show-inheritance:
    :undoc-members:

.. automodule:: eventsourcing.infrastructure.repositories.collection_repo
    :members:
    :show-inheritance:
    :undoc-members:

.. automodule:: eventsourcing.infrastructure.repositories.timebucketedlog_repo
    :members:
    :show-inheritance:
    :undoc-members:


sequenceditem
-------------

The persistence model for storing events.

.. automodule:: eventsourcing.infrastructure.sequenceditem
    :members:
    :show-inheritance:
    :undoc-members:


sequenceditemmapper
-------------------

The sequenced item mapper maps sequenced items to application-level objects.

.. automodule:: eventsourcing.infrastructure.sequenceditemmapper
    :members:
    :show-inheritance:
    :undoc-members:


snapshotting
------------

Snapshotting avoids having to replay an entire sequence of events to obtain
the current state of a projection.

.. automodule:: eventsourcing.infrastructure.snapshotting
    :members:
    :show-inheritance:
    :undoc-members:


sqlalchemy
----------

Classes for event sourcing with SQLAlchemy.

.. automodule:: eventsourcing.infrastructure.sqlalchemy.activerecords
    :members:
    :show-inheritance:
    :undoc-members:

.. automodule:: eventsourcing.infrastructure.sqlalchemy.datastore
    :members:
    :show-inheritance:
    :undoc-members:


timebucketedlog_reader
----------------------

Reader for timebucketed logs.

.. automodule:: eventsourcing.infrastructure.timebucketedlog_reader
    :members:
    :show-inheritance:
    :undoc-members:


interface
=========

The interface layer uses an application to service client requests.

notificationlog
---------------

Notification log is a pull-based mechanism for updating other applications.

.. automodule:: eventsourcing.interface.notificationlog
    :members:
    :show-inheritance:
    :undoc-members:


utils
=====

The utils package contains common functions that are used in more than one layer.

.. automodule:: eventsourcing.utils.time
    :members:
    :show-inheritance:
    :undoc-members:

.. automodule:: eventsourcing.utils.topic
    :members:
    :show-inheritance:
    :undoc-members:

.. automodule:: eventsourcing.utils.transcoding
    :members:
    :show-inheritance:
    :undoc-members:


exceptions
==========

A few exception classes are defined by the library to indicate particular kinds of error.

.. automodule:: eventsourcing.exceptions
    :members:
    :show-inheritance:
    :undoc-members:


example
=======

A simple, unit-tested, event sourced application.

application
-----------

.. automodule:: eventsourcing.example.application
    :members:
    :show-inheritance:
    :undoc-members:


domainmodel
-----------

.. automodule:: eventsourcing.example.domainmodel
    :members:
    :show-inheritance:
    :undoc-members:


infrastructure
--------------

.. automodule:: eventsourcing.example.infrastructure
    :members:
    :show-inheritance:
    :undoc-members:


interface
---------

.. automodule:: eventsourcing.example.interface.flaskapp
    :members:
    :show-inheritance:
    :undoc-members:
