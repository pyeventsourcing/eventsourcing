========
Features
========

**Generic event store** — appends and retrieves domain events. The event store uses a
sequenced item mapper with an active record strategy to map domain events
to a database in ways that can be easily extended and replaced.

..  The **sequenced item mapper**
    maps between domain events and sequenced items, the archetypal persistence model used
    by the library to store domain events. An **active record strategy** maps between
    "sequenced items" and active records (ORM). Support can be added for a new database
    management system by introducing a new active record strategy. The database schema
    can be varied by using an alternative active record class.

**Snapshotting** — avoids replaying an entire event stream to
obtain the state of an entity. A snapshot strategy is included which reuses
the capabilities of this library by implementing snapshots as events.

**Application-level encryption** — encrypts and decrypts stored events, using a cipher
strategy passed as an option to the sequenced item mapper. Can be used to encrypt some
events, or all events, or not applied at all (the default).

**Optimistic concurrency control** — can be used to ensure a distributed or
horizontally scaled application doesn't become inconsistent due to concurrent
method execution. Leverages any optimistic concurrency controls in the database
adapted by the active record strategy.

**Abstract base classes** — suggest how to structure an event sourced application.
The library has base classes for application objects, domain entities, entity repositories,
domain events of various types, mapping strategies, snapshotting strategies, cipher strategies,
etc. They are well factored, relatively simple, and can be easily extended for your own
purposes. If you wanted to create a domain model that is entirely stand-alone (recommended by
purists for maximum longevity), you might start by replicating the library classes.

**Worked examples** — a simple example application, with an example entity class,
example domain events, an example factory method, an example mutator function, and
an example database table.
