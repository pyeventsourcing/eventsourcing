Talk: How To Make A Reliable Distributed System


ABSTRACT

This talk presents design patterns for distributed systems that are reliable, scalable and maintainable. This talk follows the patterns of design that are implemented in and supported by the increasingly popular Python eventsourcing library (pypi.org/project/eventsourcing). This talk has three parts: Part I shows how to make a domain model with event-sourced aggregates; Part II shows how to make an application with an event-sourced domain model; and Part III shows how to make a reliable distributed system from a set of event-sourced applications.


Part I (10 mins): How To Make Event-Sourced Aggregates

1. Domain Events
  - Domain events are “what happens” in a domain model
  - Domain event are immutable (they occur and don’t change)
  - Can have lots of different types (timestamped, versioned, hash-chained, etc)

2. Event-Sourced Aggregates
  - Aggregates provide a consistency boundary for atomic state changes
  - Command methods trigger domain objects
  - Domain events are triggered in sequential order (no “branching”)

3. Event Store
  - Adapts database infrastructure to store and retrieve domain events

4. Sequenced Item Mapper
  - Maps domain events of different types to single stored event object type

5. Record Manager (commit events atomically)
  - Writes stored event objects to particular database
  - Has uniqueness constraint on position in aggregate’s sequence
  - Can write several events in the same atomic transaction (so either full effect of a command will be recorded, or none of it will be recorded)


Problem with this simple model of events, in which each event is simply positioned in an aggregate sequence, is that we can’t efficiently propagate the state of an application comprised of many aggregates. Even if there is back-channel to indicate when there is a new sequence, we would have to poll all of them to discover new events. In other words, the problem is that the domain events aren’t also positioned in a sequence for the application....


Part II (10 mins): How To Make Event Sourced Applications

6. Persistence Subscriber
  - Listens for domain events and puts them in the event store
  - Domain model is free to publish events without being “managed objects”

7. Event-Sourced Repository
  - Dictionary-like interface, gets domain events from event store and projects them into aggregate object

8. Record Manager (commit events and notifications atomically)
  - Writes stored events to both aggregate and application sequence (uniqueness constraint on position in both aggregate and application sequence) within atomic transaction (“notification log pattern”)

9. Notification Log
  - Presents all application events in a sequence, paged as linked “archived sections” that can be cached (design from Vaughn Vernon)
  - Standard interface that can be used locally or remotely


Can now propagate the state of the application, by following the notification log, which has all the domain events of all the aggregates. But the problem is that if this application is projecting the state of another application by processing its events, we can lose position in the upstream application sequence. If there’s a power failure during the event processing, then we might need to reset and restart from the beginning. In other words, the problem is that tracking of the position in the upstream sequence isn’t stored atomically with any new domain events...


Part III (20 mins): How to Make A Reliable Distributed System

10. Notification Log Reader
  - Reads event notifications from an application’s notification log (local or remote)

11. Processing Policy
  - Responds to event notifications by calling factory methods and command method on existing aggregates, according to the type of the event

12. Record Manager (commit tracking, events, and notifications atomically)
  - Writes stored events to aggregate and application sequence, and also writes tracking record within atomic
 transaction  (“process event pattern”)

13. Pipeline Expressions
  - Associate applications, so that one can follow another

14. System Runners
  - Various running modes (single-threaded, multi-threaded, multi-processing, etc.)
  - Various IPC technology (queues, RESTful, Reactive, Thrift, etc)
  - Can introduce concrete infrastructure at runtime, allowing entire system behaviour to be defined without
 dependending on particular infrastructure

15. Multiple Pipelines
  - Allows for scaling, works especially well when application state is naturally partitioned into independent pieces (e.g. workspaces in Slack).

16. Good System Design
  - Stages of processing: A “commands” application can capture facts in the domain (as client requests), then a “core” application can process the commands into meaningful domain model aggregates, and then a “reporting” stage can project the state of the core application into summary reports for auditing or use in analytics engine. This is better than having one application per aggregate, and then having lots of loops in the pipeline expressions, which will involve recombinations and therefore indeterminacy.

17. Reliable Projection Into Custom ORM Objects
  - Above technique for reliable projection of state of one event-sourced application into state of another can be extended to involve custom ORM objects....
