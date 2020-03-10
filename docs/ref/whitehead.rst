whitehead
=========

This module contains three base classes, which distinguish between
"actual occasion" (which "domain model event" is an example of) and
"enduring object" (which "domain model aggregate" is an example of).
These terms "actual occasion" and "enduring object" are taken
from Alfred North Whitehead's Process and Reality (published 1929).
The base classes both inherit from a base class "event" because,
in Whitehead's system, an enduring object is an event, and so is
an actual occasion.

.. contents:: :local:

.. py:module:: eventsourcing.whitehead


.. automodule:: eventsourcing.whitehead
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
