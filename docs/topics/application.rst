============
Applications
============

Overview
========

The application layer combines objects from the domain and
infrastructure layers.

An application object normally has repositories and policies.
A repository allows aggregates to be retrieved by ID, using a
dictionary-like interface. Whereas aggregates implement
commands that publish events, obversely, policies subscribe to
events and then execute commands as events are received.
An application can be well understood by understanding its policies,
aggregates, commands, and events.


Application services
--------------------

An application object can have methods ("application services")
which provide a relatively simple interface for client operations,
hiding the complexity and usage of the application's domain and
infrastructure layers.

Application services can be developed outside-in, with a
test- or behaviour-driven development approach. A test suite can
be imagined as an interface that uses the application. Interfaces
are outside the scope of the application layer.


Simple application
==================

The library provides a simple application class ``SimpleApplication``
which can be constructed directly. The ``uri`` argument is an
SQLAlchemy-style database connection string.

.. code:: python

    from eventsourcing.application.simple import SimpleApplication

    app = SimpleApplication(uri='sqlite:///:memory:')


The ``SimpleApplication`` has an event store, provided by the library's
``EventStore`` class, which it uses with SQLAlchemy infrastructure.
It uses the library function ``construct_sqlalchemy_eventstore()`` to
construct its event store.

.. code:: python

    assert app.event_store


To use different infrastructure with this class, extend the class by
overriding the ``setup_event_store()`` method. Then read about the
alternatives to the defaults available in the
:doc:`infrastructure layer </topics/infrastructure>`.

The ``SimpleApplication`` also has a persistence policy, provided by the
library's ``PersistencePolicy`` class. The persistence policy appends
domain events to its event store whenever they are published.

.. code:: python

    assert app.persistence_policy


The ``SimpleApplication`` also has an aggregate repository, provided
by the library's ``EventSourcedRepository`` class. Both the persistence
policy and the repository use the event store.

.. code:: python

    assert app.repository

The aggregate repository is generic, and can retrieve all the types of
aggregate in a model.

The ``SimpleApplication`` can be used as a context manager. The library domain
entity classes can be used to create read, update, and discard entity objects.
The example below uses the ``AggregateRoot`` class directly.

.. code:: python

    from eventsourcing.domain.model.aggregate import AggregateRoot

    with app:
        obj = AggregateRoot.create()
        obj.change_attribute(name='a', value=1)
        assert obj.a == 1
        obj.save()

        # Check the repository has the latest values.
        copy = app.repository[obj.id]
        assert copy.a == 1

        # Check the aggregate can be discarded.
        copy.discard()
        copy.save()
        assert copy.id not in app.repository

        # Check optimistic concurrency control is working ok.
        from eventsourcing.exceptions import ConcurrencyError
        try:
            obj.change_attribute(name='a', value=2)
            obj.save()
        except ConcurrencyError:
            pass
        else:
            raise Exception("Shouldn't get here")


Custom application
==================

The ``SimpleApplication`` class can also be extended.

The example below shows a custom application class ``MyApplication`` that
extends ``SimpleApplication`` with application service ``create_aggregate()``
that can create new ``CustomAggregate`` entities.

.. code:: python

    class MyApplication(SimpleApplication):
        def create_aggregate(self, a):
            return CustomAggregate.create(a=1)


The application code above depends on an entity class called
``CustomAggregate``, which is defined below. It extends the
library's ``AggregateRoot`` entity with an event sourced, mutable
attribute ``a``.

.. code:: python

    from eventsourcing.domain.model.decorators import attribute

    class CustomAggregate(AggregateRoot):
        def __init__(self, a, **kwargs):
            super(CustomAggregate, self).__init__(**kwargs)
            self._a = a

        @attribute
        def a(self):
            """Mutable attribute a."""


For more sophisticated domain models, please read about the custom
entities, commands, and domain events that can be developed using
classes from the library's :doc:`domain model layer </topics/domainmodel>`.


Run the code
------------

The custom application object can be constructed.

.. code:: python

    # Construct application object.
    app = MyApplication()


The application service can be called.

.. code:: python

    # Create aggregate using application service, and save it.
    aggregate = app.create_aggregate(a=1)
    aggregate.save()


The aggregate now exists in the repository. An existing aggregate can
be retrieved by ID using the repository's dictionary-like interface.

.. code:: python

    # Aggregate is in the repository.
    assert aggregate.id in app.repository

    # Get aggregate using dictionary-like interface.
    aggregate = app.repository[aggregate.id]

    assert aggregate.a == 1


Changes to the aggregate's attribute ``a`` are visible in
the repository, but only after the aggregate has been saved.

.. code:: python

    # Change attribute value.
    aggregate.a = 2
    aggregate.a = 3

    # Don't forget to save!
    aggregate.save()

    # Retrieve again from repository.
    aggregate = app.repository[aggregate.id]

    # Check attribute has new value.
    assert aggregate.a == 3


The aggregate can be discarded. After being saved, a discarded
aggregate will no longer be available in the repository.

.. code:: python

    # Discard the aggregate.
    aggregate.discard()

    # Check discarded aggregate no longer exists in repository.
    assert aggregate.id not in app.repository


Attempts to retrieve an aggregate that does not
exist will cause a ``KeyError`` to be raised.

.. code:: python

    # Fail to get aggregate from dictionary-like interface.
    try:
        app.repository[aggregate.id]
    except KeyError:
        pass
    else:
        raise Exception("Shouldn't get here")


Application events
------------------

It is always possible to get the domain events for an aggregate,
by using the application's event store method ``get_domain_events()``.

.. code:: python

    events = app.event_store.get_domain_events(originator_id=aggregate.id)
    assert len(events) == 4

    assert events[0].originator_id == aggregate.id
    assert isinstance(events[0], CustomAggregate.Created)
    assert events[0].a == 1

    assert events[1].originator_id == aggregate.id
    assert isinstance(events[1], CustomAggregate.AttributeChanged)
    assert events[1].name == '_a'
    assert events[1].value == 2

    assert events[2].originator_id == aggregate.id
    assert isinstance(events[2], CustomAggregate.AttributeChanged)
    assert events[2].name == '_a'
    assert events[2].value == 3

    assert events[3].originator_id == aggregate.id
    assert isinstance(events[3], CustomAggregate.Discarded)


Sequenced items
---------------

It is also possible to get the sequenced item namedtuples for an aggregate,
by using the event store's active record strategy method ``get_items()``.

.. code:: python

    items = app.event_store.active_record_strategy.get_items(aggregate.id)
    assert len(items) == 4

    assert items[0].originator_id == aggregate.id
    assert items[0].event_type == 'eventsourcing.domain.model.aggregate#AggregateRoot.Created'
    assert '"a":1' in items[0].state
    assert '"timestamp":' in items[0].state

    assert items[1].originator_id == aggregate.id
    assert items[1].event_type == 'eventsourcing.domain.model.aggregate#AggregateRoot.AttributeChanged'
    assert '"name":"_a"' in items[1].state
    assert '"timestamp":' in items[1].state

    assert items[2].originator_id == aggregate.id
    assert items[2].event_type == 'eventsourcing.domain.model.aggregate#AggregateRoot.AttributeChanged'
    assert '"name":"_a"' in items[2].state
    assert '"timestamp":' in items[2].state

    assert items[3].originator_id == aggregate.id
    assert items[3].event_type == 'eventsourcing.domain.model.aggregate#AggregateRoot.Discarded'
    assert '"timestamp":' in items[3].state


Close
-----

If the application isn't being used as a context manager, then it is useful to
unsubscribe any handlers subscribed by the policies (avoids dangling handlers
being called inappropriately, if the process isn't going to terminate immediately,
such as when this documentation is tested as part of the library's test suite).

.. code:: python

    # Clean up.
    app.close()



.. Todo: Something about using uuid5 to make UUIDs from things like email addresses.

.. Todo: Something about using application log to get a sequence of all events.

.. Todo: Something about using a policy to update views from published events.

.. Todo: Something about using a policy to update a register of existant IDs from published events.

.. Todo: Something about having a worker application, that has policies that process events received by a worker.

.. Todo: Something about having a policy to publish events to worker applications.

.. Todo: Something like a message queue strategy strategy.

.. Todo: Something about publishing events to a message queue.

.. Todo: Something about receiving events in a message queue worker.

.. Todo: Something about publishing events to a message queue.

.. Todo: Something about receiving events in a message queue worker.

