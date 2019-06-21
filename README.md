# Event Sourcing in Python

[![Latest Release](https://badge.fury.io/py/eventsourcing.svg)](https://pypi.org/project/eventsourcing/)
[![Build Status](https://travis-ci.org/johnbywater/eventsourcing.svg?branch=master)](https://travis-ci.org/johnbywater/eventsourcing)
[![Coverage Status](https://coveralls.io/repos/github/johnbywater/eventsourcing/badge.svg?branch=master)](https://coveralls.io/github/johnbywater/eventsourcing)

A library for event sourcing in Python.

## Installation

Use pip to install the [stable distribution](https://pypi.org/project/eventsourcing/) from
the Python Package Index.

    $ pip install eventsourcing


Please refer to the [documentation](https://eventsourcing.readthedocs.io/) for installation and usage guides.

Register questions, requests and [issues on GitHub](https://github.com/johnbywater/eventsourcing/issues).

There is a [Slack channel](https://join.slack.com/t/eventsourcinginpython/shared_invite/enQtMjczNTc2MzcxNDI0LTUwZGQ4MDk0ZDJmZmU0MjM4MjdmOTBlZGI0ZTY4NWIxMGFkZTcwNmUxM2U4NGM3YjY5MTVmZTBiYzljZjI3ZTE)
for this project, which you are [welcome to join](https://join.slack.com/t/eventsourcinginpython/shared_invite/enQtMjczNTc2MzcxNDI0LTUwZGQ4MDk0ZDJmZmU0MjM4MjdmOTBlZGI0ZTY4NWIxMGFkZTcwNmUxM2U4NGM3YjY5MTVmZTBiYzljZjI3ZTE).


## Features

**Event store** — stores and retrieves domain events. Uses a
sequenced item mapper with a record strategy to map domain events
to database records in ways that can be easily extended and replaced.

**Abstract base classes** — suggest how to structure an event sourced
application. The library has base classes for application objects,
domain entities, entity repositories, domain events of various types,
mapping strategies, snapshotting strategies, cipher strategies, etc.
They are well factored, relatively simple, and can be easily extended
for your own purposes. If you wanted to create a domain model that is
entirely stand-alone (recommended by purists for maximum longevity),
you might start by replicating the library classes.

**Notifications and projections** — reliable propagation of application
events with pull-based notifications allows the application state to be
projected accurately into replicas, indexes, and view models.

**Process and system** — scalable event processing with application
pipelines. Parallel pipelines are synchronised with causal dependencies.
Runnable with single thread, multiprocessing on a single machine, and in
a cluster of machines using the actor model.

**Snapshotting** — avoids replaying an entire event stream to
obtain the state of an entity. A snapshot strategy is included which
reuses the capabilities of this library by implementing snapshots as
events.

**Optimistic concurrency control** — can be used to ensure a distributed
or horizontally scaled application doesn't become inconsistent due to
concurrent method execution. Leverages any optimistic concurrency
controls in the database adapted by the record manager.

**Data integrity** — stored events can be hashed to check data integrity
of individual records, so you cannot lose information in transit or get
database corruption without being able to detect it. Sequences of events
can be hash-chained, and the entire sequence of events checked for
integrity, so if the last hash can be independently validated, then
so can the entire sequence.

**Application-level encryption** — encrypts and decrypts stored events,
using a cipher strategy passed as an option to the sequenced item
mapper. Can be used to encrypt some events, or all events, or not
applied at all (the default).

**Worked examples** — a simple example application, with an example
entity class, example domain events, and an example database table.
Plus lots of examples in the documentation.


## Synopsis

Define a domain model. Here we define a model with one aggregate root
class called "World", which has a command method called "make_it_so" that
triggers a domain event called "SomethingHappened", which mutates the
aggregate by appending the "what" of the domain event to the "history"
of the world.

```python
from eventsourcing.domain.model.aggregate import AggregateRoot


class World(AggregateRoot):

    def __init__(self, **kwargs):
        super(World, self).__init__(**kwargs)
        self.history = []

    def make_it_so(self, something):
        self.__trigger_event__(World.SomethingHappened, what=something)

    class SomethingHappened(AggregateRoot.Event):
        def mutate(self, aggregate):
            aggregate.history.append(self.what)
```

Generate a cipher key (optional).

```python
from eventsourcing.utils.random import encode_random_bytes

# Keep this safe.
cipher_key = encode_random_bytes(num_bytes=32)
```

Configure environment variables (optional).

```python
import os

# Cipher key (random bytes encoded with Base64).
os.environ['CIPHER_KEY'] = cipher_key

# SQLAlchemy-style database connection string.
os.environ['DB_URI'] = 'sqlite:///:memory:'
```

Run the code. Construct application and use as context manager.

```python
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.exceptions import ConcurrencyError

with SQLAlchemyApplication(persist_event_type=World.Event) as app:

    # Create new aggregate.
    world = World.__create__()

    # Aggregate not yet in repository.
    assert world.id not in app.repository

    # Execute commands.
    world.make_it_so('dinosaurs')
    world.make_it_so('trucks')

    # View current state of aggregate object.
    assert world.history[0] == 'dinosaurs'
    assert world.history[1] == 'trucks'

    # Note version of object at this stage.
    version = world.__version__

    # Execute another command.
    world.make_it_so('internet')

    # Store pending domain events.
    world.__save__()

    # Aggregate now exists in repository.
    assert world.id in app.repository

    # Replay stored events for aggregate.
    copy = app.repository[world.id]

    # View retrieved aggregate.
    assert isinstance(copy, World)
    assert copy.history[0] == 'dinosaurs'
    assert copy.history[1] == 'trucks'
    assert copy.history[2] == 'internet'

    # Verify retrieved state (cryptographically).
    assert copy.__head__ == world.__head__

    # Delete aggregate.
    world.__discard__()
    world.__save__()

    # Discarded aggregate not found.
    assert world.id not in app.repository
    try:
        # Repository raises key error.
        app.repository[world.id]
    except KeyError:
        pass
    else:
        raise Exception("Shouldn't get here")

    # Get historical state (at version from above).
    old = app.repository.get_entity(world.id, at=version)
    assert old.history[-1] == 'trucks' # internet not happened
    assert len(old.history) == 2

    # Optimistic concurrency control (no branches).
    old.make_it_so('future')
    try:
        old.__save__()
    except ConcurrencyError:
        pass
    else:
        raise Exception("Shouldn't get here")

    # Check domain event data integrity (happens also during replay).
    events = app.event_store.get_domain_events(world.id)
    last_hash = ''
    for event in events:
        event.__check_hash__()
        assert event.__previous_hash__ == last_hash
        last_hash = event.__event_hash__

    # Verify stored sequence of events against known value.
    assert last_hash == world.__head__

    # Check records are encrypted (values not visible in database).
    record_manager = app.event_store.record_manager
    items = record_manager.get_items(world.id)
    for item in items:
        for what in ['dinosaurs', 'trucks', 'internet']:
            assert what not in item.state
        assert world.id == item.originator_id

    # Project application event notifications.
    from eventsourcing.interface.notificationlog import NotificationLogReader
    reader = NotificationLogReader(app.notification_log)
    notification_ids = [n['id'] for n in reader.read()]
    assert notification_ids == [1, 2, 3, 4, 5]

    # - create two more aggregates
    world = World.__create__()
    world.__save__()

    world = World.__create__()
    world.__save__()

    # - get the new event notifications from the reader
    notification_ids = [n['id'] for n in reader.read()]
    assert notification_ids == [6, 7]
```

The double leading and trailing underscore naming style, seen above,
is used consistently in the library's domain entity and event
base classes for attribute and method names, so that developers can
begin with a clean namespace. The intention is that the library
functionality is included in the application by aliasing these library
names with names that work within the project's ubiquitous language.

This style breaks PEP8, but it seems worthwhile in order to keep the
"normal" Python object namespace free for domain modelling. It is a style
used by other libraries (such as SQLAlchemy and Django) for similar reasons.

The exception is the ``id`` attribute of the domain entity base class,
which is assumed to be required by all domain entities (or aggregates) in
all domains.


## Project

This project is [hosted on GitHub](https://github.com/johnbywater/eventsourcing).
