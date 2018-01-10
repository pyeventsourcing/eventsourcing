# Event Sourcing in Python

[![Build Status](https://secure.travis-ci.org/johnbywater/eventsourcing.png)](https://travis-ci.org/johnbywater/eventsourcing)
[![Coverage Status](https://coveralls.io/repos/github/johnbywater/eventsourcing/badge.svg#)](https://coveralls.io/github/johnbywater/eventsourcing)

A library for event sourcing in Python.

## Installation

Use pip to install the [stable distribution](https://pypi.python.org/pypi/eventsourcing) from
the Python Package Index.

    $ pip install eventsourcing
    

Please refer to the [documentation](http://eventsourcing.readthedocs.io/) for installation and usage guides.

Register questions, requests and [issues on GitHub](https://github.com/johnbywater/eventsourcing/issues).

There is a [Slack channel](https://eventsourcinginpython.slack.com/messages/) for this project, which you
are [welcome to join](https://join.slack.com/t/eventsourcinginpython/shared_invite/enQtMjczNTc2MzcxNDI0LTUwZGQ4MDk0ZDJmZmU0MjM4MjdmOTBlZGI0ZTY4NWIxMGFkZTcwNmUxM2U4NGM3YjY5MTVmZTBiYzljZjI3ZTE).


## Features

**Event store** — appends and retrieves domain events. Uses a
sequenced item mapper with an active record strategy to map domain events
to databases in ways that can be easily extended and replaced.

**Data integrity** - stored events can be hashed to check data integrity of individual
records, so you cannot lose information in transit or get database corruption without
being able to detect it. Sequences of events can be hash-chained, and the entire sequence
of events checked for integrity, so if the last hash can be independently validated, then
so can the entire sequence.

**Optimistic concurrency control** — can be used to ensure a distributed or
horizontally scaled application doesn't become inconsistent due to concurrent
method execution. Leverages any optimistic concurrency controls in the database
adapted by the active record strategy.

**Application-level encryption** — encrypts and decrypts stored events, using a cipher
strategy passed as an option to the sequenced item mapper. Can be used to encrypt some
events, or all events, or not applied at all (the default).

**Snapshotting** — avoids replaying an entire event stream to
obtain the state of an entity. A snapshot strategy is included which reuses
the capabilities of this library by implementing snapshots as events.

**Abstract base classes** — suggest how to structure an event sourced application.
The library has base classes for application objects, domain entities, entity repositories,
domain events of various types, mapping strategies, snapshotting strategies, cipher strategies,
etc. They are well factored, relatively simple, and can be easily extended for your own
purposes. If you wanted to create a domain model that is entirely stand-alone (recommended by
purists for maximum longevity), you might start by replicating the library classes.

**Worked examples** — a simple example application, with an example entity class,
example domain events, and an example database table. Plus lots of examples in the documentation. 


## Synopsis

Develop a domain model.

```python
from eventsourcing.domain.model.aggregate import AggregateRoot


class World(AggregateRoot):

    def __init__(self, **kwargs):
        super(World, self).__init__(**kwargs)
        self.history = []

    def make_it_so(self, something):
        self.__trigger_event__(World.SomethingHappened, what=something)
    
    class SomethingHappened(AggregateRoot.Event):
        def mutate(self, obj):
            obj.history.append(self)
```

Generate a cipher key (optional).

```python
from eventsourcing.utils.random import encode_random_bytes

# Keep this safe.
cipher_key = encode_random_bytes(num_bytes=32)
```

Configure environment variables.

```python
import os

# Cipher key (random bytes encoded with Base64).
os.environ['CIPHER_KEY'] = cipher_key

# SQLAlchemy-style database connection string. 
os.environ['DB_URI'] = 'sqlite:///:memory:'
```

Run the code.

```python
from eventsourcing.application.simple import SimpleApplication
from eventsourcing.exceptions import ConcurrencyError

# Construct simple application (used here as a context manager).
with SimpleApplication() as app:

    # Create new aggregate.
    world = World.__create__()

    # Aggregate not yet in repository.
    assert world.id not in app.repository

    # Execute commands.
    world.make_it_so('dinosaurs')
    world.make_it_so('trucks')
    
    # View current state of aggregate object.
    assert world.history[0].what == 'dinosaurs'
    assert world.history[1].what == 'trucks'

    # Note version of object at this stage.
    version = world.__version__ 

    # Execute another command.
    world.make_it_so('internet')

    # Store pending domain events.
    world.__save__()

    # Aggregate now exists in repository.
    assert world.id in app.repository

    # Replay stored events.
    copy = app.repository[world.id]

    # View retrieved state.
    assert isinstance(copy, World)
    assert copy.history[0].what == 'dinosaurs'
    assert copy.history[1].what == 'trucks'
    assert copy.history[2].what == 'internet'

    # Verify retrieved state (cryptographically).
    assert copy.__head__ == world.__head__

    # Delete.
    world.__discard__()

    # Repository raises key error (when aggregate not found).
    assert world.id not in app.repository
    try:
        app.repository[world.id]
    except KeyError:
        pass
    else:
        raise Exception("Shouldn't get here")

    # Get historical state (at version from above).
    old = app.repository.get_entity(world.id, at=version)
    assert old.history[-1].what == 'trucks' # internet not happened
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
    active_record_strategy = app.event_store.active_record_strategy
    items = active_record_strategy.get_items(world.id)
    for item in items:
        for what in ['dinosaurs', 'trucks', 'internet']:         
            assert what not in item.state
        assert world.id == item.originator_id 
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
