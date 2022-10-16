.. _Searchable content example:

Application 5 - Searchable content
==================================

This example demonstrates how to extend the library's application recorder classes
to support full text search queries in an event-sourced application with both
`PostgreSQL <https://www.postgresql.org/docs/current/textsearch.html>`_ and
`SQLite <https://www.sqlite.org/fts5.html>`_.

Application
-----------

The application class ``SearchableContentApplication`` extends the ``WikiApplication``
class presented in the :doc:`content management example </topics/examples/content-management>`.
It extends the :func:`~eventsourcing.application.Application.save` method by using the variable keyword parameters (``**kwargs``)
of the application :func:`~eventsourcing.application.Application.save` method to pass down to the recorder extra
information that will be used to update a searchable index of the event-sourced
content. It also introduces a ``search()`` method that expects a ``query``
argument and returns a list of pages.

.. literalinclude:: ../../../eventsourcing/examples/searchablecontent/application.py


Persistence
-----------

The recorder classes ``SearchableContentApplicationRecorder`` extend the PostgreSQL
and SQLite ``ApplicationRecorder`` classes by creating a table that contains the current
page body text. They define SQL statements that insert, update, and search the rows
of the table using search query syntax similar to the one used by web search engines.
They define a ``search_page_bodies()`` method which returns the page slugs for page
bodies that match the given search query.

.. literalinclude:: ../../../eventsourcing/examples/searchablecontent/persistence.py

The application recorder classes extend the ``_insert_events()`` method by inserting
and updating rows, according to the information passed down from the application
through the :func:`~eventsourcing.application.Application.save` method's variable keyword parameters.

The infrastructure factory classes ``SearchableContentInfrastructureFactory`` extend the
PostgreSQL and SQLite ``Factory`` class by overriding the ``application_recorder()`` method
so that a ``SearchableContentApplicationRecorder`` is constructed as the application recorder.


PostgreSQL
----------

The PostgreSQL recorder uses a GIN index and the ``websearch_to_tsquery()`` function.

.. literalinclude:: ../../../eventsourcing/examples/searchablecontent/postgres.py


SQLite
------

The SQLite recorder uses a virtual table and the ``MATCH`` operator.

.. literalinclude:: ../../../eventsourcing/examples/searchablecontent/sqlite.py


Test case
---------

The test case ``SearchableContentTestCase`` uses the application to create three
pages, for 'animals', 'plants' and 'minerals'. Content is added to the pages. The
content is searched with various queries and the search results are checked. The
test is executed twice, with the application configured for both PostgreSQL and SQLite.

.. literalinclude:: ../../../eventsourcing/examples/searchablecontent/test_searchablecontent.py
