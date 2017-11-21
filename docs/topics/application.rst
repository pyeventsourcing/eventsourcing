============
Applications
============

The application layer combines objects from the domain and
infrastructure layers.

An application object can have methods ("application services")
which provide a relatively simple interface for clients operations,
hiding the complexity and usage of the application's domain and
infrastructure layers.

An application object can have repositories, that provide a
dictionary-like interface, so that aggregates can be retrieved by ID.
In general, aggregates implement commands that publish events.

An application object can have policies. In general, policies receive
events and execute commands. For example, in an event sourced application,
a persistence policy can append domain events to an event store whenever
they are published.

Although an application can be used by interfaces, interfaces are outside
the scope of the application layer.

Application services are most effectively developed outside-in, with
test- or behaviour-driven development. Tests can be imagined as the first
interface that uses the application.


Event sourced application
=========================

The example below shows an event sourced application object class. When constructed, it constructs
an event store that uses the library's infrastructure with SQLAlchemy. A domain model with one
domain entity type called ``CustomAggregate`` is defined for the application using the library's
``AggregateRoot`` entity class.

The application object class below has a persistence policy. It uses the library class
``PersistencePolicy``. The persistence policy stores domain events when they are published,
and requires an event store when it is constructed.

An event sourced application normally has aggregate repositories that are event sourced. The application below
has an event sourced repository for ``CustomAggregate`` instances. It uses the library class
``EventSourceRepository``, which requires an event store when it is constructed. An application can have many
repositories, normally one for each type of aggregate in the application's domain model.

The application below also has an application service called ``create_aggregate()`` which can be used
to create new ``CustomAggregate`` instances. The ``CustomAggregate`` is a very simple aggregate, which
has an event sourced attribute called `a`. To create such an aggregate, a value for `a` must be provided.

.. code:: python

    from uuid import uuid4

    from eventsourcing.application.policies import PersistencePolicy
    from eventsourcing.domain.model.aggregate import AggregateRoot
    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
    from eventsourcing.infrastructure.sqlalchemy.factory import construct_sqlalchemy_eventstore
    from eventsourcing.domain.model.decorators import attribute


    class Application(object):
        def __init__(self, session):
            # Construct event store.
            self.event_store = construct_sqlalchemy_eventstore(
                session=session
            )
            # Construct a persistence policy.
            self.persistence_policy = PersistencePolicy(
                event_store=self.event_store
            )
            # Construct an event sourced repository.
            self.repository = EventSourcedRepository(
                event_store=self.event_store,
                mutator=CustomAggregate._mutate
            )

        def create_aggregate(self, a):
            aggregate_id = uuid4()
            domain_event = CustomAggregate.Created(a=1, originator_id=aggregate_id)
            entity = CustomAggregate._mutate(event=domain_event)
            entity._publish(domain_event)  # Pending save().
            return entity

        def close(self):
            self.persistence_policy.close()


    class CustomAggregate(AggregateRoot):
        def __init__(self, a, **kwargs):
            super(CustomAggregate, self).__init__(**kwargs)
            self._a = a

        @attribute
        def a(self):
            """
            Event sourced attribute 'a'.
            """


The application above is constructed with a database session object.
The ``active_record_class`` of the event store's active record strategy
can be used to setup a table in the database for storing events.

.. code:: python

    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings

    # Define database settings.
    settings = SQLAlchemySettings()

    # Setup connection to database.
    datastore = SQLAlchemyDatastore(settings=settings)
    datastore.setup_connection()

    # Construct application with database session.
    app = Application(session=datastore.session)

    # Setup table in database.
    datastore.setup_table(app.event_store.active_record_strategy.active_record_class)


A new aggregate instance can be created with the application service ``create_aggregate()``.

.. code:: python


    # Create aggregate using application service.
    aggregate = app.create_aggregate(a=1)

    # Don't forget to save!
    aggregate.save()

    # Aggregate is in the repository.
    assert aggregate.id in app.repository

    # Remember the aggregate's ID.
    aggregate_id = aggregate.id

    # Forget the aggregate (will still saved be in the database).
    del(aggregate)


An existing aggregate can be recovered by ID using the dictionary-like interface of the aggregate repository.

.. code:: python

    # Get aggregate using dictionary-like interface.
    aggregate = app.repository[aggregate_id]

    assert aggregate.a == 1


Changes to the aggregate's attribute `a` are visible in the repository, but only after the aggregate has been saved.

.. code:: python

    aggregate.a = 2
    aggregate.a = 3

    # Don't forget to save!
    aggregate.save()

    del(aggregate)

    aggregate = app.repository[aggregate_id]

    assert aggregate.a == 3


The aggregate can be discarded. After being saved, a discarded aggregate will not be available in the repository.

.. code:: python

    aggregate.discard()

    # Don't forget to save!
    aggregate.save()

    # Discarded aggregate no longer in repository.
    assert aggregate_id not in app.repository

    # Fail to get aggregate from dictionary-like interface.
    try:
        app.repository[aggregate_id]
    except KeyError:
        pass
    else:
        raise Excpetion("Shouldn't get here.")



It is always possible to get the domain events for an aggregate, using the application's event store method
``get_domain_events()``.

.. code:: python

    events = app.event_store.get_domain_events(originator_id=aggregate_id)
    assert len(events) == 4

    assert events[0].originator_id == aggregate_id
    assert isinstance(events[0], CustomAggregate.Created)
    assert events[0].a == 1

    assert events[1].originator_id == aggregate_id
    assert isinstance(events[1], CustomAggregate.AttributeChanged)
    assert events[1].name == '_a'
    assert events[1].value == 2

    assert events[2].originator_id == aggregate_id
    assert isinstance(events[2], CustomAggregate.AttributeChanged)
    assert events[2].name == '_a'
    assert events[2].value == 3

    assert events[3].originator_id == aggregate_id
    assert isinstance(events[3], CustomAggregate.Discarded)


It is also possible to get the sequenced item namedtuples for an aggregate, using the application's event store's
active record strategy method ``get_items()``.

.. code:: python

    items = app.event_store.active_record_strategy.get_items(aggregate_id)
    assert len(items) == 4

    assert items[0].originator_id == aggregate_id
    assert items[0].event_type == 'eventsourcing.domain.model.aggregate#AggregateRoot.Created'
    assert items[0].state.startswith('{"a":1,"timestamp":')

    assert items[1].originator_id == aggregate_id
    assert items[1].event_type == 'eventsourcing.domain.model.aggregate#AggregateRoot.AttributeChanged'
    assert items[1].state.startswith('{"name":"_a",')

    assert items[2].originator_id == aggregate_id
    assert items[2].event_type == 'eventsourcing.domain.model.aggregate#AggregateRoot.AttributeChanged'
    assert items[2].state.startswith('{"name":"_a",')

    assert items[3].originator_id == aggregate_id
    assert items[3].event_type == 'eventsourcing.domain.model.aggregate#AggregateRoot.Discarded'
    assert items[3].state.startswith('{"timestamp":')


It is useful to unsubscribe any handlers subscribed by the policies (avoids dangling
handlers being called inappropriately, if the process isn't going to terminate immediately).

.. code:: python

    app.close()


Todo: Something about using uuid5 to make UUIDs from things like email addresses.

Todo: Something about using application log to get a sequence of all events.

Todo: Something about using a policy to update views from published events.

Todo: Something about using a policy to update a register of existant IDs from published events.

Todo: Something about having a worker application, that has policies that process events received by a worker.

Todo: Something about having a policy to publish events to worker applications.

Todo: Something like a message queue strategy strategy.

Todo: Something about publishing events to a message queue.

Todo: Something about receiving events in a message queue worker.

Todo: Something about publishing events to a message queue.

Todo: Something about receiving events in a message queue worker.

