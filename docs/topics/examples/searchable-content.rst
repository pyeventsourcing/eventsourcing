.. _Searchable content example:

Application 5 - Searchable content
==================================

This example demonstrates how to extend the library's application recorder classes
to support full text search queries in an event-sourced application with both
`PostgreSQL <https://www.postgresql.org/docs/current/textsearch.html>`_ and
`SQLite <https://www.sqlite.org/fts5.html>`_.

Application
-----------

The application class ``SearchableContentApplication`` extends the ``ContentManagementApplication``
class presented in :doc:`/topics/examples/content-management`.
Its :func:`~eventsourcing.application.Application.save` method sets the variable keyword
parameters ``insert_pages`` and ``update_pages``. It also introduces a ``search()`` method that
expects a ``query`` argument and returns a list of pages. The application's recorders are expected
to be receptive to these variable keyword parameters and to support the ``search_pages()`` function.

.. literalinclude:: ../../../eventsourcing/examples/searchablecontent/application.py


Persistence
-----------

The recorder class ``SearchableContentRecorder`` extends the ``AggregateRecorder`` by
defining abstract methods to search and select pages. These methods will be implemented
for both PostgreSQL and SQLite, which will also create custom tables for page content with
a full text search indexes.

.. literalinclude:: ../../../eventsourcing/examples/searchablecontent/persistence.py

The ``_insert_events()`` methods of the PostgreSQL and SQLite recorders are extended, so that
rows are inserted and updated, according to the information passed down from the application
in the variable keyword arguments ``insert_pages`` and ``update_pages``.


PostgreSQL
----------

The PostgreSQL recorder uses a GIN index and the ``websearch_to_tsquery()`` function.
The PostgreSQL :class:`~eventsourcing.postgres.Factory` class is extended to involve this custom recorder
in a custom PostgreSQL persistence module so that it can be used by the ``ContentManagementApplication``.

.. literalinclude:: ../../../eventsourcing/examples/searchablecontent/postgres.py

SQLite
------

The SQLite recorder uses a virtual table and the ``MATCH`` operator.
The SQLite :class:`~eventsourcing.sqlite.Factory` class is extended to involve this custom recorder
in a custom SQLite persistence module so that it can be used by the ``ContentManagementApplication``.

.. literalinclude:: ../../../eventsourcing/examples/searchablecontent/sqlite.py


Test case
---------

The test case ``SearchableContentApplicationTestCase`` uses the ``SearchableContentApplication`` to
create three pages, for 'animals', 'plants' and 'minerals'. Content is added to the pages. The
content is searched with various queries and the search results are checked. The
test case is executed twice, once with the PostgreSQL persistence module, and once with the
SQLite persistence module.

.. literalinclude:: ../../../eventsourcing/examples/searchablecontent/test_application.py
