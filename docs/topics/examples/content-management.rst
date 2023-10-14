.. _Content management example:

Application 3 - Content management
==================================

This example demonstrates the use of :ref:`namespaced IDs <Namespaced IDs>` for both
discovery of aggregate IDs and implementation of an application-wide rule (or "invariant").
This example also involves :ref:`event-sourced logs <event-sourced-log>`,
automatic :ref:`snapshotting <automatic-snapshotting>`, and the use of the declarative
syntax for domain models with :ref:`non-trivial command methods <non-trivial-command-methods>`.

This example also shows how to use a thread-specific context variable to set the value
of a common event attribute without cluttering all the command methods with the same
argument. In this example the ID of the user is recorded on each event, but the same
technique can be used to set correlation and causation IDs on all events in a domain
model.

Application
-----------

The ``ContentManagementApplication`` class defines methods to create a new page, to get
the details for a page by its slug, to update the title of a page referenced by its slug,
to update the body of a page, and to change the page slug.

To get to a page, the slug is used to identify an index, and the index is used to get the
page ID, and then the page ID is used to get the body and title of the page. To change a
slug, the index objects for the old and the new are identified, the page ID is removed as
the reference from the old index and set as the reference on the new index. The indexes
are also used to implement a application-wide rule (or "invariant") that a slug can be
used by only one page, such that if an attempt is made to change the slug of one page
to a slug that is already being used by another page, then a ``SlugConflictError``
will be raised, and no changes made.

The application also demonstrates the "event-sourced log" recipe, by showing how all
the IDs of the ``Page`` aggregates can be listed, by logging the page ID in a sequence
of stored events, and then selecting from this sequence when presenting a list of pages.

Please note, although the domain model (see below) involves a ``user_id`` event attribute,
none of the application command methods mention a ``user_id`` argument. Instead the value
is set in a context variable by callers of the application command methods (see the test below).

.. literalinclude:: ../../../eventsourcing/examples/contentmanagement/application.py


Domain model
------------

In the domain model below, the ``Page`` aggregate has a base class ``Event``
which is defined with a ``user_id`` data class ``field``. This base aggregate
event class is inherited by all its concrete aggregate event classes.
The ``user_id`` field is defined not to be included in the ``__init__`` method
of the aggregate's event classes (``init=False``), and so it does not need to
be matched by parameters in the aggregate command method signatures. Instead,
this field gets the event attribute value from a Python context variable
(``default_factory=user_id_cvar.get``).

The ``update_body()`` command method does some work on the command arguments
before the ``BodyUpdated`` event is triggered. It creates a "diff" of the
current version of the ``body`` and the new version. It then triggers an event,
which contains the diff, by calling ``_update_body()``. The event is applied
to the ``body`` by patching the current version of the ``body`` with the diff
that has been encapsulated by the event object.

The ``Index`` aggregate has a version-5 UUID which is a function of a ``slug``.
The ``Index`` and ``Page`` aggregates are used in combination to maintain editable
pages of text, with editable titles, and with editable "slugs" that can be used in page URLs.

A ``PageLogged`` event is also defined, and used to define a "page log" in the application.

.. literalinclude:: ../../../eventsourcing/examples/contentmanagement/domainmodel.py


The ``create_diff()`` and ``apply_patch()`` functions use the Unix command line
tools ``patch`` and ``diff``.

.. literalinclude:: ../../../eventsourcing/examples/contentmanagement/utils.py


Test case
---------

The test case below sets a user ID in the context variable. A page is created
and updated in various ways. At the end, all the page events are checked to
make sure they all have the user ID that was set in the context variable.

.. literalinclude:: ../../../eventsourcing/examples/contentmanagement/test.py
