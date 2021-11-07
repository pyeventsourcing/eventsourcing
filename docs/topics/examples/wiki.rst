.. _Wiki example:

Wiki application
=========================

This example demonstrates the use of version 5 UUIDs, the use of the declarative
syntax for domain models with a "non-trivial" command method, automatic snapshotting,
automatic setting of a common attribute on all events without needing to mention this
attribute in the command methods, and a recipe for an event-sourced log.

Domain model
------------

In the domain model below, the ``Page`` aggregate has a base class ``Event``
which is defined with a ``user_id`` dataclass ``field`` that is defined not
to be included in its ``__init__`` method, and so does not need to be matched
by parameters in the command method signatures. It has a default factory which
gets the event attribute value from a Python context variable. This base aggregate
event class is inherited by all its concrete aggregate event classes. The
event attribute value can be accessed inside the decorated methods in two
different ways: by configuring the ``@event`` decorator with the ``inject_event``
argument and using the ``__event__`` value injected into function globals,
and more simply by mentioning the ``user_id`` as an optional argument in the
method signature.

The ``update_body()`` command method is does a "non-trival" amount of work
before the ``BodyUpdated`` event is triggered, by creating a "diff" of the
current version of the ``body`` and the new version. It then triggers an event,
which contains the diff. The event is applied to the ``body`` by "patching" the
current version of the ``body`` with this diff.

The ``Index`` aggregate has a version 5 UUID which is a function of a ``slug``.
The ``Index`` and ``Page`` aggregates are used in combination to maintain editable
pages of text, with editable titles, and with editable "slugs" that can be used in page URLs.

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
