# Event Sourcing in Python

[![Build Status](https://secure.travis-ci.org/johnbywater/eventsourcing.png)](https://travis-ci.org/johnbywater/eventsourcing)
[![Coverage Status](https://coveralls.io/repos/github/johnbywater/eventsourcing/badge.svg)](https://coveralls.io/github/johnbywater/eventsourcing)

A library for event sourcing in Python.

## Installation

Use pip to install the [stable distribution](https://pypi.python.org/pypi/eventsourcing) from
the Python Package Index.

    $ pip install eventsourcing

Please refer to [the documentation](http://eventsourcing.readthedocs.io/) for installation and usage guides.

# Features

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

```python
import os

from eventsourcing.application.simple import SimpleApplication
from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.exceptions import ConcurrencyError

# Configure environment.
os.environ['AES_CIPHER_KEY'] = '0123456789abcdef'

# Domain model aggregate.
class World(AggregateRoot):
    def __init__(self, *args, **kwargs):
        super(World, self).__init__(*args, **kwargs)
        self.history = []

    # Command triggers events.
    def make_it_so(self, something):
        self._trigger(World.SomethingHappened, what=something)

    # Nested entity events.
    class SomethingHappened(AggregateRoot.Event):
        def mutate(self, obj):
            obj = super(World.SomethingHappened, self).mutate(obj)
            obj.history.append(self)
            return obj
            

# Application as context manager.
with SimpleApplication(uri='sqlite:///:memory:') as app:

    # Aggregate factory.
    world = World.create()
    
    # Execute commands.
    world.make_it_so('dinosaurs')
    world.make_it_so('trucks')
    version = world.version # note version at this stage
    world.make_it_so('internet')

    # View current state.
    assert world.history[0].what == 'dinosaurs'
    assert world.history[1].what == 'trucks'
    assert world.history[2].what == 'internet'

    # Publish pending events.
    world.save()

    # Retrieve aggregate from stored events.
    obj = app.repository[world.id]
    assert obj.__class__ == World
    
    # Verify retrieved aggregate state.
    assert obj.__head__ == world.__head__

    # View retrieved aggregate state.
    assert obj.id == world.id
    assert obj.history[0].what == 'dinosaurs'
    assert obj.history[1].what == 'trucks'
    assert obj.history[2].what == 'internet'
    
    # Discard aggregate.
    world.discard()
    world.save()

    # Not found in repository. 
    assert world.id not in app.repository
    try:
        app.repository[world.id]
    except KeyError:
        pass
    else:
        raise Exception("Shouldn't get here")

    # Optimistic concurrency control.
    obj.make_it_so('future')
    try:
        obj.save()
    except ConcurrencyError:
        pass
    else:
        raise Exception("Shouldn't get here")

    # Historical state at version from above.
    old = app.repository.get_entity(world.id, lt=version)
    assert len(old.history) == 2
    assert old.history[-1].what == 'trucks' # internet not happened
    
    # Data integrity (also checked when events were replayed).
    events = app.event_store.get_domain_events(world.id)
    assert len(events) == 5
    last_hash = ''
    for event in events:
        event.validate()
        assert event.originator_hash == last_hash
        last_hash = event.event_hash

    # Encrypted records.
    items = app.event_store.active_record_strategy.get_items(world.id)
    assert len(items) == 5
    for item in items:
        assert item.originator_id == world.id
        assert 'dinosaurs' not in item.state
        assert 'trucks' not in item.state
        assert 'internet' not in item.state
```

## Project

This project is [hosted on GitHub](https://github.com/johnbywater/eventsourcing).
Please [register your questions, requests and any other issues](https://github.com/johnbywater/eventsourcing/issues).

## Slack Channel

There is a [Slack channel](https://eventsourcinginpython.slack.com/messages/@slackbot/) for this project, which you are [welcome to join](https://join.slack.com/t/eventsourcinginpython/shared_invite/enQtMjczNTc2MzcxNDI0LTUwZGQ4MDk0ZDJmZmU0MjM4MjdmOTBlZGI0ZTY4NWIxMGFkZTcwNmUxM2U4NGM3YjY5MTVmZTBiYzljZjI3ZTE).
