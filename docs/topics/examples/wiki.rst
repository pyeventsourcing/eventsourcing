.. _Wiki example:

Wiki application
=========================

This example demonstrates the use of version 5 UUIDs. It also shows
the use of the declarative syntax for domain models with a "non-trivial"
command method, that is a command method that actually does some work
before triggering an aggregate event (see ``update_body()``). This example
also demonstrates automatic snapshotting at regular intervals.

This example also demonstrates how to define a common attribute that is set
on all events of an aggregate without needing to define a matching argument
on all of the command methods (see ``user_id`` on base ``Event`` class on
``Page`` aggregate class). This example also shows two different way in which
the value of this common event attribute can be accessed inside a decorated
common method (set ``inject_event`` as a decorator arg, or mention the value
in the method signature with a default so you don't need to pass a value when
calling the method).


Domain model
------------

In the domain model below, the ``Page`` aggregate has a base class ``Event``
which is defined with a ``user_id`` dataclass ``field`` that is defined not
to be included in its init method. It has a default factory which gets the
event attribute value from a Python context variable. This base aggregate
event class is inherited by all its concrete aggregate event classes. The
event attribute value is accessed inside the decorated methods.

The ``update_body()`` method creates a "diff" from the current to the new version
of the ``body`` text. It then triggers an event, which contains the diff, which
is applied to the ``body`` text by "patching" the current version of the ``body``
text.

The ``Index`` aggregate has a version 5 UUID which is a function of a ``slug``.

These aggregates can be used in combination to maintain editable pages of text,
with editable titles, and with editable "slugs" that can be used in page URLs.

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


.. literalinclude:: ../../../eventsourcing/examples/wiki/application.py


Test case
---------

The test case below sets a user ID in the context variable. A page is created
and updated in various ways. At the end, all the page events are checked to
make sure they all have the user ID that was set in the context variable.

.. literalinclude:: ../../../eventsourcing/examples/wiki/test.py
