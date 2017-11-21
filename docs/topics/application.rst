============
Applications
============

The application layer combines objects from the domain and
infrastructure layers.

An application object can have methods ("application services")
which provide a relatively simple interface for clients operations,
hiding the complexity and usage of the application's domain and
infrastructure objects.

Application services are most effectively developed outside-in, with
test- or behaviour-driven development.

An application object can have repositories, that provide a
dictionary-like interface, so that aggregates can be retrieved by ID.
In general, aggregates implement commands that publish events.

An application object can have policies. In general, policies receive
events and execute commands. For example, in an event sourced application,
a persistence policy can append domain events to an event store whenever
they are published.

Although an application can be used by interfaces, interfaces are outside
the scope of the application layer.


Event sourced application
=========================

An event sourced application will have aggregate repositories that are event
sourced. In this library, that means the event sourced repositories require
an event store.

An event sourced application also has a persistence policy. The persistence
policy also requires an event store.

The example below shows an event sourced application object that uses SQLAlchemy.

.. code:: python

    from uuid import uuid4

    from eventsourcing.domain.model.aggregate import AggregateRoot
    from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository
    from eventsourcing.infrastructure.eventstore import EventStore
    from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
    from eventsourcing.infrastructure.sqlalchemy.factory import construct_sqlalchemy_eventstore

    class Application(object):
        def __init__(self, session):
            self.event_store = construct_sqlalchemy_eventstore(session)
            self.repository = EventSourcedRepository(
                event_store=self.event_store,
                mutator=CustomAggregate._mutate,
            )

    class CustomAggregate(AggregateRoot):
        def __init__(self, a, **kwargs):
            super(CustomAggregate, self).__init__(**kwargs)


    datastore = SQLAlchemyDatastore(settings=SQLAlchemySettings())
    datastore.setup_connection()

    event_store = construct_sqlalchemy_eventstore(datastore.session)
    datastore.setup_table(event_store.active_record_strategy.active_record_class)

    assert isinstance(event_store, EventStore)

    aggregate_id = uuid4()
    aggregate_version = 0
    domain_event = CustomAggregate.Created(
        a=1,
        originator_id=aggregate_id,
        originator_version=aggregate_version,
    )

    # Todo: Replace this with a persistence policy.
    event_store.append(domain_event)
    events = event_store.get_domain_events(originator_id=aggregate_id)
    assert len(events) == 1
    assert events[0] == domain_event

    app = Application(session=datastore.session)

    entity = app.repository[aggregate_id]

    assert entity.id == aggregate_id
