========
Features
========

**Event store** — appends and retrieves domain events. The event store uses a
"sequenced item mapper" and an "active record strategy" to map domain events
to a database in ways that can be easily substituted.

**Persistence policy** — subscribes to receive published domain events.
Appends received domain events to an event store whenever a domain event is
published. Domain events are typically published by the methods of an entity.

**Event player** — reconstitutes entities by replaying events, optionally with
snapshotting. An event player is used by an entity repository to determine the
state of an entity. The event player retrieves domain events from the event store.

**Sequenced item mapper** — maps between domain events and "sequenced items", the archetype
persistence model used by the library to store domain events. The library supports two
different kinds of sequenced item: items that are sequenced by an increasing series
of integers; and items that are sequenced in time. They support two different kinds of
domain events: events of versioned entities (e.g. an aggregate in domain driven design),
and unversioned timestamped events (e.g. entries in a log).

**Active record strategy** — maps between "sequenced items" and database records (ORM).
Support can be added for a new database schema by introducing a new active record strategy.

**Application-level encryption** — encrypts and decrypts stored events, using a cipher
strategy passed as an option to the sequenced item mapper. Can be used to encrypt some
events, or all events, or not applied at all (the default). Included is a cipher strategy
which uses a standard AES cipher, by default in CBC mode with 128 bit blocksize and a 16
byte encryption key, and which generates a unique 16 byte initialization vector for each
encryption. In this cipher strategy, data is compressed before it is encrypted, which can
mean application performance is improved when encryption is enabled.

**Optimistic concurrency control** — can be used to ensure a distributed or
horizontally scaled application doesn't become inconsistent due to concurrent
method execution. Leverages any optimistic concurrency controls in the database
adapted by the stored event repository. For example the Cassandra database, which implements
the Paxos protocol, can accomplish linearly-scalable distributed optimistic concurrency
control, guaranteeing sequential consistency of the events of an entity. It is also possible to serialize calls to the methods of an
entity, but that is out of the scope of this package — if you wish to do that,
perhaps something like `Zookeeper <https://zookeeper.apache.org/>`__ might help.

**Snapshotting** — avoids replaying an entire event stream to
obtain the state of an entity. A snapshot strategy is included which reuses
the capabilities of this library by implementing snapshots as time-sequenced domain
events. It can easily be substituted with one that uses a dedicated table for snapshots.

**Abstract base classes** — suggest how to structure an event sourced application.
The library has base classes for application objects, domain entities, entity repositories,
domain events of various types, mapping strategies, snapshotting strategies, cipher strategies,
test cases, etc. They are well factored, relatively simple, and can be easily extended for your own
purposes. If you wanted to create a domain model that is entirely stand-alone (recommended by
purists for maximum longevity), you might start by copying the library classes.

**Synchronous publish-subscribe mechanism** — propagates events from publishers to subscribers.
Stable and deterministic, with handlers called in the order they are registered, and with which
calls to publish events do not return until all event subscribers have returned. In general,
subscribers are policies of the application, which may execute further commands whenever a
particular kind of event is received. Publishers of domain events are typically methods of domain entities.

**Worked examples** — a simple worked example application with an example
entity class, with example domain events, an example factory method, an example mutator function,
and an example database table.
