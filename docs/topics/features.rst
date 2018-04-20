========
Features
========

**Event store** — appends and retrieves domain events. Uses a
sequenced item mapper with a record manager to map domain events
to database records in ways that can be easily extended and replaced.

**Data integrity** — Sequences of events can be hash-chained, and the entire sequence
of events checked for integrity. If the last hash can be independently validated, then
so can the entire sequence. Events records can be encrypted with an authenticated encryption
algorithm, so you cannot lose information in transit or at rest, or get database corruption
without being able to detect it.

**Optimistic concurrency control** — can be used to ensure a distributed or
horizontally scaled application doesn't become inconsistent due to concurrent
method execution. Leverages any optimistic concurrency controls in the database
adapted by the record manager.

**Application-level encryption** — encrypts and decrypts stored events, using a cipher
strategy passed as an option to the sequenced item mapper. Can be used to encrypt some
events, or all events, or not applied at all (the default).

**Snapshotting** — avoids replaying an entire event stream to
obtain the state of an entity. A snapshot strategy is included which reuses
the capabilities of this library by implementing snapshots as events.

**Notifications and projections** — reliable propagation of application
events with pull-based notifications allows the application state to be
projected accurately into replicas, indexes, view models, and other applications.

**Process and systems** — scalable event processing with application pipelines. Parallel
pipelines are synchronised with causal dependencies. Runnable with single thread,
multiprocessing on a single machine, and in a cluster of machines using the actor
model.

**Abstract base classes** — suggest how to structure an event sourced application.
The library has base classes for application objects, domain entities, entity repositories,
domain events of various types, mapping strategies, snapshotting strategies, cipher strategies,
etc. They are well factored, relatively simple, and can be easily extended for your own
purposes. If you wanted to create a domain model that is entirely stand-alone (recommended by
purists for maximum longevity), you might start by replicating the library classes.

**Worked examples** — a simple example application, with an example entity class,
example domain events, and an example database table. Plus lots of examples in the documentation.
