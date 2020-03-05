========
Features
========

Core features
=============

**Event store** — appends and retrieves domain events. Uses a
sequenced item mapper with a record manager to map domain events
to database records in ways that can be easily extended and replaced.

**Layer base classes** — suggest how to structure an event sourced application.
The library has base classes for application objects, domain entities, entity repositories,
domain events of various types, mapping strategies, snapshotting strategies, cipher strategies,
etc. They are well factored, relatively simple, and can be easily extended for your own
purposes. If you wanted to create a domain model that is entirely stand-alone (recommended by
purists for maximum longevity), you might start by replicating the library classes.

**Notifications and projections** — reliable propagation of application
events with pull-based notifications allows the application state to be
projected accurately into replicas, indexes, view models, and other applications.

**Process and systems** — scalable event processing with application pipelines. Parallel
pipelines are synchronised with causal dependencies. Runnable with single thread,
multiprocessing on a single machine, and in a cluster of machines using the actor
model.

Additional features
===================

**Optimistic concurrency control** — ensures a distributed or
horizontally scaled application doesn't become inconsistent due to concurrent
method execution. Leverages any optimistic concurrency controls in the database
adapted by the record manager.

**Snapshotting** — avoids replaying an entire event stream to
obtain the state of an entity. A snapshot strategy is included which reuses
the capabilities of this library by implementing snapshots as events.

**Application-level encryption** — encrypts and decrypts stored events, using a cipher
strategy passed as an option to the sequenced item mapper. Can be used to encrypt some
events, or all events, or not applied at all (the default).

**Versioning** - allows model changes to be introduced after an application has been
deployed. The state of an older version can be upcast to be compatible with a new version.
Both domain events and domain entity classes can be versioned. Stored events and snapshots
can be upcast from older versions to new versions before the event or entity object is
reconstructed.

**Data integrity** — Sequences of events can be hash-chained, and the entire sequence
of events checked for integrity. If the last hash can be independently validated, then
so can the entire sequence. Events records can be encrypted with an authenticated encryption
algorithm, so you cannot lose information in transit or at rest, or get database corruption
without being able to detect it.

**Worked examples** — simple example application and systems, with an example entity class,
example domain events, and an example database table. Plus lots of examples in the documentation.
