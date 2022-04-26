.. _Searchable timestamps example:

Application 5 - Searchable timestamps
=====================================

This example demonstrates how to extend the library's PostgreSQL application recorder
to support retrieving aggregates at a particular point in time.

Application
-----------

The application class ``SearchableTimestampsApplication`` extends the
``BookingApplication`` presented in the cargo shipping example.
It overrides the application's ``construct_factory()`` method by
constructing an extended version of the library's PostgreSQL infrastructure
factory. It extends the application ``_record()`` method by
setting in the processing event a list of event timestamp data tuples
that will be used by the recorder to insert timestamps into an index.
It also introduces a ``get_cargo_at_timestamp()`` method that expects a
``timestamp`` argument, as well as a ``tracking_id`` argument, and then
returns a ``Cargo`` aggregate as it was at the specified time.

.. literalinclude:: ../../../eventsourcing/examples/searchabletimestamps/application.py


Persistence
-----------

The recorder class ``SearchableTimestampsApplicationRecorder`` creates a table that
contains rows with the originator ID, timestamp, and originator version of `Cargo`
events. It defines SQL statements that insert and select from the rows of the table.

It extends the ``_insert_events()`` method by inserting rows, according to the
event timestamp data passed down from the application. It defines a method
``get_version_at_timestamp()`` method returns the version of an aggregate
at a particular time.

The infrastructure factory class ``SearchableTimestampsInfrastructureFactory``
extends the PosgreSQL ``Factory`` class by overriding the ``application_recorder()``
method so that the ``SearchableTimestampsApplicationRecorder`` is constructed as the
application recorder.

.. literalinclude:: ../../../eventsourcing/examples/searchabletimestamps/persistence.py


Test case
---------

The test case below evolves the state of a ``Cargo`` aggregate. The aggregate
is then reconstructed as it was at particular times in its evolution.

.. literalinclude:: ../../../eventsourcing/examples/searchabletimestamps/test.py
