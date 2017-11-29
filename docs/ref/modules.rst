===========
Module docs
===========

This document describes the packages, modules, classes, functions and other code
details of the library.

-------------
eventsourcing
-------------

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


domain.model
============

aggregate
---------

.. automodule:: eventsourcing.domain.model.aggregate
    :members:
    :show-inheritance:
    :undoc-members:


array
-----

.. automodule:: eventsourcing.domain.model.array
    :members:
    :show-inheritance:
    :undoc-members:


collection
----------

.. automodule:: eventsourcing.domain.model.decorators
    :members:
    :show-inheritance:
    :undoc-members:


entity
------

.. automodule:: eventsourcing.domain.model.entity
    :members:
    :show-inheritance:
    :undoc-members:


events
------

.. automodule:: eventsourcing.domain.model.events
    :members:
    :show-inheritance:
    :undoc-members:


snapshot
--------

.. automodule:: eventsourcing.domain.model.snapshot
    :members:
    :show-inheritance:
    :undoc-members:


timebucketedlog
---------------

.. automodule:: eventsourcing.domain.model.timebucketedlog
    :members:
    :show-inheritance:
    :undoc-members:


infrastructure
==============

activerecord
------------

.. automodule:: eventsourcing.infrastructure.activerecord
    :members:
    :show-inheritance:
    :undoc-members:

cassandra
---------

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

.. automodule:: eventsourcing.infrastructure.datastore
    :members:
    :show-inheritance:
    :undoc-members:


eventplayer
-----------

.. automodule:: eventsourcing.infrastructure.eventplayer
    :members:
    :show-inheritance:
    :undoc-members:


eventsourcedrepository
----------------------

.. automodule:: eventsourcing.infrastructure.eventsourcedrepository
    :members:
    :show-inheritance:
    :undoc-members:


eventstore
----------

.. automodule:: eventsourcing.infrastructure.eventstore
    :members:
    :show-inheritance:
    :undoc-members:


integersequencegenerators
-------------------------

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

.. automodule:: eventsourcing.infrastructure.iterators
    :members:
    :show-inheritance:
    :undoc-members:


repositories
------------

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

.. automodule:: eventsourcing.infrastructure.sequenceditem
    :members:
    :show-inheritance:
    :undoc-members:


sequenceditemmapper
-------------------

.. automodule:: eventsourcing.infrastructure.sequenceditemmapper
    :members:
    :show-inheritance:
    :undoc-members:


snapshotting
------------

.. automodule:: eventsourcing.infrastructure.snapshotting
    :members:
    :show-inheritance:
    :undoc-members:


sqlalchemy
----------

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

.. automodule:: eventsourcing.infrastructure.timebucketedlog_reader
    :members:
    :show-inheritance:
    :undoc-members:


interface
=========

notificationlog
---------------

.. automodule:: eventsourcing.interface.notificationlog
    :members:
    :show-inheritance:
    :undoc-members:


utils
=====

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

.. automodule:: eventsourcing.exceptions
    :members:
    :show-inheritance:
    :undoc-members:


example
=======

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
