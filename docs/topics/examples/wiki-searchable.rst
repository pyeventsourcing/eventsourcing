.. _Searchable wiki example:

Application 4 - Searchable content
==================================

This example demonstrates how to extend the library's PostgreSQL application recorder
to support `full text search <https://www.postgresql.org/docs/current/textsearch.html_>`_
queries in an event-sourced application.

Application
-----------

The application class ``SearchableWikiApplication`` extends the ``WikiApplication``
class presented in the previous example. It overrides the application's
``construct_factory()`` method by constructing an extended version of
the library's PostgreSQL infrastructure factory (see below). It extends
the ``save()`` method by using the variable keyword parameters (``**kwargs``)
of the application ``save()`` method to pass down to the recorder extra
information that will be used to update a searchable index of the event-sourced
content. And it introduces a ``search()`` method that expects a ``query``
argument and returns a list of pages.

.. literalinclude:: ../../../eventsourcing/examples/searchablewiki/application.py


Persistence
-----------

The infrastructure class ``SearchableWikiInfrastructureFactory`` extends the PosgreSQL ``Factory``
class by overriding the ``application_recorder()`` so that the ``SearchableWikiApplicationRecorder``
is constructed for the application.

The recorder class ``SearchableWikiApplicationRecorder`` creates a table that contains the
current page body text, and a GIN index that allows the text to be searched. It
defines SQL statements that insert, update, and search the rows of the table
using search query syntax similar to the one used by web search engines.

It extends the ``_insert_events()`` method by inserting and updating rows,
according to the information passed down from the application through the
``save()`` method's variable keyword parameters. It introduces a ``search_page_bodies()``
method which returns the page slugs for page bodies that match the given search query.

.. literalinclude:: ../../../eventsourcing/examples/searchablewiki/persistence.py


Test case
---------

The test case below creates three pages for animals, plants, and minerals.
Content is added to the pages. The pages are searched with various queries
and the search results are checked.

.. literalinclude:: ../../../eventsourcing/examples/searchablewiki/test.py
