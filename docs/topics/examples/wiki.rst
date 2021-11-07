.. _Wiki example:

Wiki application
=========================

This example demonstrates the use of version 5 UUIDs.

It shows the use of the declarative syntax for domain models with a
"non-trivial" command method. That is, a command method that actually
does some work before triggering an aggregate event (see ``update_body()``
and ``_update_body()``).

This example demonstrates automatic snapshotting at regular intervals.

This example demonstrates how to define a common attribute that is set
on all events of an aggregate without needing to define a matching argument
on all of the command methods (see ``user_id`` on base ``Event`` class on
``Page`` aggregate class). This example also shows two different ways in which
the value of this common event attribute can be accessed inside a decorated
common method.

This example also shows a recipe for an event-sourced log, using a sequence
of events for logging page IDs, and then selecting sections from this sequence.


Domain model
------------

In the domain model below, the ``Page`` aggregate has a base class ``Event``
which is defined with a ``user_id`` dataclass ``field`` that is defined not
to be included in its ``__init__`` method and so does not need to be matched
by parameters in the command method signatures. It has a default factory which
gets the event attribute value from a Python context variable. This base aggregate
event class is inherited by all its concrete aggregate event classes. The
event attribute value can be accessed inside the decorated methods in two
different ways: by using the ``__event__`` value injected into function globals,
and by mentioning the ``user_id`` as an optional argument in the method signature.

The ``update_body()`` method creates a "diff" from the current version of the ``body``
to the new version. It then triggers an event, which contains the diff, and which
is applied to the ``body`` by "patching" the current version of the ``body``.

The ``Index`` aggregate has a version 5 UUID which is a function of a ``slug``.

These aggregates can be used in combination to maintain editable pages of text,
with editable titles, and with editable "slugs" that can be used in page URLs.

A ``PageLogged`` event is also defined, and used to define a "page log" in the application.

.. literalinclude:: ../../../eventsourcing/examples/wiki/domainmodel.py


Utils
-----

The ``create_diff()`` and ``apply_patch()`` functions use the Unix command line
tools ``patch`` and ``diff``.

.. literalinclude:: ../../../eventsourcing/examples/wiki/utils.py


Application
-----------

The application provides methods to create a new page, get the details for a page by its
slug, to update the title of a page referenced by its slug, to update the body of a page,
and to change the slug indexes. None of these methods mention a ``user_id`` argument.
To get to a page, the slug is used to identify an index, and the index is used
to get the page ID, and then the page ID is used to get the body and title of
the page.

The application also demonstrates how the IDs of a type of aggregate can be listed, by
logging the IDs when the aggregate is created using a sequence of stored events, and
then selecting from this sequence when presenting a list of the the aggregates.

.. literalinclude:: ../../../eventsourcing/examples/wiki/application.py


Test case
---------

The test case below sets a user ID in the context variable. A page is created
and updated in various ways. At the end, all the page events are checked to
make sure they all have the user ID that was set in the context variable.

.. literalinclude:: ../../../eventsourcing/examples/wiki/test.py
