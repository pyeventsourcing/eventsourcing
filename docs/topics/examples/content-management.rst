.. _Content management example:

Application 3 - Content management
==================================

This example demonstrates the use of :ref:`namespaced IDs <Namespaced IDs>` for both
discovery of aggregate IDs and implementation of an application-wide rule (or "invariant").
This example also involves :ref:`event-sourced logs <event-sourced-log>`,
automatic :ref:`snapshotting <automatic-snapshotting>`, and the use of the declarative
syntax for domain models with :ref:`non-trivial command methods <non-trivial-command-methods>`.

This example also shows how to set event metadata. In this example, the ID of a user is recorded
in the metadata of each event. The same technique can be used to set correlation IDs and causation
IDs.

Domain model
------------

The :class:`~examples.contentmanagement.domainmodel.Page` class is an aggregate defined
to have a :data:`~examples.contentmanagement.domainmodel.Page.title`,
a :data:`~examples.contentmanagement.domainmodel.Page.slug`,
a :data:`~examples.contentmanagement.domainmodel.Page.body`,
and a :data:`~examples.contentmanagement.domainmodel.Page.modified_by` attribute.
It defines a aggregate event base class, :class:`~examples.contentmanagement.domainmodel.Page.Event`,
which has a :data:`~examples.contentmanagement.domainmodel.Page.Event.user_id` attribute that is
defined with a data class field object. All the aggregate event classes of :class:`~examples.contentmanagement.domainmodel.Page`
inherit from its :class:`~examples.contentmanagement.domainmodel.Page.Event` class. The
:class:`~examples.contentmanagement.domainmodel.Page.Event` class defines a
:func:`~examples.contentmanagement.domainmodel.Page.Event.apply` method that sets the
aggregate's :data:`~examples.contentmanagement.domainmodel.Page.modified_by` attribute
to the value of the event metadata's ``"user_id"`` value. Event metadata is obtained
when events are triggered, by using :func:`~eventsourcing.domain.get_metadata_from_context`,
and supplied whilst application commands are executed, by using :func:`~eventsourcing.domain.put_metadata_in_context`.

.. literalinclude:: ../../../examples/contentmanagement/domainmodel.py
    :pyobject: Page

The :func:`~examples.contentmanagement.domainmodel.Page.update_body` command method is a
:ref:`non-trivial command methods <non-trivial-command-methods>`, in that is does some work
on the command method arguments before triggering a domain event: it creates a "diff" of the
current version of the :data:`~examples.contentmanagement.domainmodel.Page.body` and the
new version. For this reason, it is not decorated with the event decorator.

After creating a "diff" of the page page, it calls the "private" method
:func:`~examples.contentmanagement.domainmodel.Page._update_body`, which is decorated with the
event decorator, and so triggers a
:class:`~examples.contentmanagement.domainmodel.Page.BodyUpdated` event. The event is applied
to the page's :data:`~examples.contentmanagement.domainmodel.Page.body` by patching the
current value with the :class:`~examples.contentmanagement.domainmodel.Page.BodyUpdated.diff`
that has been encapsulated by the event object.

The :class:`~examples.contentmanagement.domainmodel.Slug` assists the domain model by carrying
a :data:`~examples.contentmanagement.domainmodel.Slug.page_id`. This aggregate's ID is a
version-5 UUID, that is a function of its :data:`~examples.contentmanagement.domainmodel.Slug.name`.

The :class:`~examples.contentmanagement.domainmodel.Slug` and :class:`~examples.contentmanagement.domainmodel.Page`
aggregates are used in combination to maintain editable pages of text, with editable titles, and with editable
"slugs" that can be used in page URLs. The slug's name is taken from the URL, and used to discover the aggregate ID
of the page it is currently associated with.

.. literalinclude:: ../../../examples/contentmanagement/domainmodel.py
    :pyobject: Slug


A ``PageLogged`` event is also defined, and used to define a "page log". The page log
can be used to discover all the pages that have been created.

.. literalinclude:: ../../../examples/contentmanagement/domainmodel.py
    :pyobject: PageLogged


Application
-----------

The :class:`~examples.contentmanagement.application.ContentManagement` application encapsulates
the :class:`~examples.contentmanagement.domainmodel.Page` and :class:`~examples.contentmanagement.domainmodel.Slug`
aggregates. It defines methods to create a new page, to get the content of a page by its slug, and to update
the title, body, and slug of a page.

.. literalinclude:: ../../../examples/contentmanagement/application.py
    :pyobject: ContentManagement

To get to a page, a slug aggregate ID is computed from a slug string, and the slug aggregate is used to
get the page aggregate ID.

To change a page's slug, the slug aggregates for the old and the new slug strings are obtained,
the page ID is removed as the page ID of the old slug, and it is set as the page ID of the new slug.
The slugs are also used to implement an application-wide rule (or "invariant") that a slug can be
used by only one page. If an attempt is made to change the slug of one page to a slug that is already
being used by another page, then a :class:`~examples.contentmanagement.domainmodel.SlugConflictError`
will be raised, and no changes made.

The application also demonstrates the "event-sourced log" recipe, by showing how all
the IDs of the :class:`~examples.contentmanagement.domainmodel.Page` aggregates can be listed, by logging
the page ID in a sequence of stored events, and then selecting from this sequence when presenting a list
of pages.

The application also demonstrates the automatic snapshotting of aggregates at regular intervals. In
this case, the class attribute :data:`~examples.contentmanagement.application.ContentManagement.snapshotting_intervals`
specifies that a page will be snapshotted every 5 events.


Diff and patch utilities
------------------------

The ``create_diff()`` and ``apply_diff()`` functions use the Unix command line
tools ``diff`` and ``patch``.

.. literalinclude:: ../../../examples/contentmanagement/utils.py
    :pyobject: create_diff

.. literalinclude:: ../../../examples/contentmanagement/utils.py
    :pyobject: apply_diff

.. literalinclude:: ../../../examples/contentmanagement/utils.py
    :pyobject: run


Test case
---------

The :class:`~examples.contentmanagement.test_contentmanagement.TestContentManagement` test case creates and updates pages
in various ways. It sets a user ID in the metadata context variable using the context manager
:func:`~eventsourcing.domain.put_metadata_in_context` before application methods are called.
At the end, all the page events are checked to make sure they all have the user ID that was
set in the context variable.

.. literalinclude:: ../../../examples/contentmanagement/test_contentmanagement.py
    :pyobject: TestContentManagement


Code reference
--------------

.. automodule:: examples.contentmanagement.domainmodel
    :show-inheritance:
    :member-order: bysource
    :members:
    :private-members: _update_body
    :undoc-members:

.. automodule:: examples.contentmanagement.application
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.contentmanagement.utils
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

.. automodule:: examples.contentmanagement.test_contentmanagement
    :show-inheritance:
    :member-order: bysource
    :members:
    :undoc-members:

