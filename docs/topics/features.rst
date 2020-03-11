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

**Process and systems** — scalable event processing with application pipelines. Runnable
with single thread, multiprocessing on a single machine, and in a cluster of machines
using the actor model. Parallel pipelines are synchronised with causal dependencies.

Additional features
===================

**Versioning** - allows model changes to be introduced after an application
has been deployed. Both domain events and domain entity classes can be versioned.
The recorded state of an older version can be upcast to be compatible with a new
version. Stored events and snapshots are upcast from older versions
to new versions before the event or entity object is reconstructed.

**Snapshotting** — avoids replaying an entire event stream to
obtain the state of an entity. A snapshot strategy is included which reuses
the capabilities of this library by implementing snapshots as events.

**Hash chaining** — Sequences of events can be hash-chained, and the entire sequence
of events checked for data integrity. Information lost in transit or on the disk from
database corruption can be detected. If the last hash can be independently validated,
then so can the entire sequence.

**Correlation and causation IDs** - Domain events can easily be given correlation and
causation IDs, which allows a story to be traced through a system of applications.

**Compression** - reduces the size of stored domain events and snapshots, usually
by around 25% to 50% of the original size. Compression reduces the size of data
in the database and decreases transit time across a network.

**Application-level encryption** — encrypts and decrypts stored events and snapshots,
using a cipher strategy passed as an option to the sequenced item mapper. Can be used
to encrypt some events, or all events, or not applied at all (the default). This means
data will be encrypted in transit across a network ("on the wire") and at disk level
including backups ("at rest"), which is a legal requirement in some jurisdictions
when dealing with personally identifiable information (PII) for example the EU's GDPR.

**Optimistic concurrency control** — ensures a distributed or horizontally scaled
application doesn't become inconsistent due to concurrent method execution. Leverages
optimistic concurrency controls in adapted database management systems.

**Worked examples** — simple example application and systems, with an example entity
class, example domain events, and an example database table. Plus lots of examples
in the documentation.
