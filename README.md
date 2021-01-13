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

There is a [Slack channel](https://join.slack.com/t/eventsourcinginpython/shared_invite/enQtMjczNTc2MzcxNDI0LTJjMmJjYTc3ODQ3M2YwOTMwMDJlODJkMjk3ZmE1MGYyZDM4MjIxODZmYmVkZmJkODRhZDg5N2MwZjk1YzU3NmY)
for this project, which you are [welcome to join](https://join.slack.com/t/eventsourcinginpython/shared_invite/enQtMjczNTc2MzcxNDI0LTJjMmJjYTc3ODQ3M2YwOTMwMDJlODJkMjk3ZmE1MGYyZDM4MjIxODZmYmVkZmJkODRhZDg5N2MwZjk1YzU3NmY).


## Features

**Domain model and application classes** — base classes for event sourced
domain models and applications. Applications can be developed that are
independent of any particular infrastructure.

**Event mapper with extensible transcoder** — extensible convertion of
domain events with custom value objects to standard stored event
objects. Individual transcodings for custom value objects can be
defined and registered.

**Event recorders** — inserts and selects stored event objects in a data
store. Uses a standard interface defined in an abstract base class, allowing
database management systems to be easily adapted. Recorders for SQLite and
PostgreSQL recorders are included. A fast "plain old Python object" recorder
is also included that supports rapid application development. Recorders
for other database management systems, including cloud-native databases,
are available.

**Generic event store** — stores and retrieves domain model event objects in a
database management system using extensible event mapper and custom event recorders.

**Application-level encryption** — encrypts and decrypts stored events and snapshots,
using a cipher strategy passed as an option to the event mapper. Can be used
to encrypt some events, or all events, or not applied at all (the default). This means
data will be encrypted in transit across a network ("on the wire") and at disk level
including backups ("at rest"), which is a legal requirement in some jurisdictions
when dealing with personally identifiable information (PII) for example the EU's GDPR.

**Compression** - compresses and decompresses stored events and snapshots, using
a compression strategy passed as an option to the event mapper. Reduces the size
of stored events and snapshots, usually by around 25% to 50% of the original size.
Compression reduces the size of data in the database and decreases transit time
across a network.

**Optimistic concurrency control** — ensures the recorded state of a distributed
or horizontally scaled application doesn't become inconsistent due to concurrent
method execution. Leverages optimistic concurrency controls in adapted database
management systems.

**Notification logs and reader** — reliable propagation of application
state. Pull-based event notifications allows the application state to
be projected accurately into replicas, indexes, view models, and other
applications.

**Snapshotting** — avoids replaying an entire event stream to
obtain the state of an entity.

**Process and systems** — reliable event-driven systems can be defined
independently of particular infrastructure. Systems can be run with a
single thread, multiple threads, or across a network.

**Worked examples** — library includes a collection of example applications and systems.



## Synopsis

Define a domain model. Here we define a model with an aggregate
called "World", which has a command method called "make_it_so", that
triggers a domain event called "SomethingHappened", which applies the
event to the aggregate by appending the "what" of the domain event to
the "history" of the world.

```python

from uuid import uuid4

from eventsourcing.domain import Aggregate


class World(Aggregate):

    def __init__(self, **kwargs):
        super(World, self).__init__(**kwargs)
        self.history = []

    @classmethod
    def create(self):
        return self._create_(World.Created, uuid=uuid4())

    def make_it_so(self, something):
        self._trigger_(World.SomethingHappened, what=something)

    class SomethingHappened(Aggregate.Event):
        what: str

        def apply(self, aggregate):
            aggregate.history.append(self.what)

    def discard(self):
        self._trigger_(self.Discarded)

    class Discarded(Aggregate.Event):
        def mutate(self, obj):
            super().mutate(obj)
            return None

```

Define a test that exercises the domain model with an application.

```python
from eventsourcing.application import AggregateNotFound, Application
from eventsourcing.system import NotificationLogReader


def test(app: Application):

    # Create a new aggregate.
    world = World.create()

    # Unsaved aggregate not yet in application repository.
    try:
        app.repository.get(world.uuid)
    except AggregateNotFound:
        pass

    # Execute aggregate commands.
    world.make_it_so('dinosaurs')
    world.make_it_so('trucks')

    # View current state of aggregate object.
    assert world.history[0] == 'dinosaurs'
    assert world.history[1] == 'trucks'

    # Note version of object at this stage.
    version = world.version

    # Execute another command.
    world.make_it_so('internet')

    # Store pending domain events.
    app.save(world)

    # Aggregate now exists in repository.
    assert app.repository.get(world.uuid)

    # Show the notification log has four items.
    assert len(app.log['1,10'].items) == 4

    # Replay stored events for aggregate.
    copy = app.repository.get(world.uuid)

    # View retrieved aggregate.
    assert isinstance(copy, World)
    assert copy.history[0] == 'dinosaurs'
    assert copy.history[1] == 'trucks'
    assert copy.history[2] == 'internet'

    # Discard aggregate.
    world.discard()
    app.save(world)

    # Discarded aggregate not found.
    try:
        app.repository.get(world.uuid)
    except AggregateNotFound:
        pass

    # Get historical state (at version from above).
    old = app.repository.get(world.uuid, at=version)
    assert old.history[-1] == 'trucks' # internet not happened
    assert len(old.history) == 2

    # Optimistic concurrency control (no branches).
    from eventsourcing.persistence import RecordConflictError

    old.make_it_so('future')
    try:
        app.save(old)
    except RecordConflictError:
        pass
    else:
        raise Exception("Shouldn't get here")

    # Project application event notifications.
    reader = NotificationLogReader(app.log)
    notification_ids = [n.id for n in reader.read(start=1)]
    assert notification_ids == [1, 2, 3, 4, 5]

    # - create two more aggregates
    world2 = World.create()
    app.save(world2)

    world3 = World.create()
    app.save(world3)

    # - get the new event notifications from the reader
    notification_ids = [n.id for n in reader.read(start=6)]
    assert notification_ids == [6, 7]
```

Run the code in default "development" environment (uses default "Plain Old Python Object"
infrastructure, with no encryption and no compression).

```python

# Construct an application object.
app = Application()

# Run the test.
test(app)

# Records are not encrypted (values are visible in stored data).
def count_visible_values(app):
    num_visible_values = 0
    values = [b'dinosaurs', b'trucks', b'internet']
    reader = NotificationLogReader(app.log)
    for notification in reader.read(start=1):
        for what in values:
            if what in notification.state:
                num_visible_values += 1
                break
    return num_visible_values

assert count_visible_values(app) == 3
```

Configure "production" environment using SQLite infrastructure.

```python
import os

from eventsourcing.cipher import AESCipher

# Generate a cipher key (keep this safe).
cipher_key = AESCipher.create_key(num_bytes=32)

# Cipher key.
os.environ['CIPHER_KEY'] = cipher_key
# Cipher topic.
os.environ['CIPHER_TOPIC'] = "eventsourcing.cipher:AESCipher"
# Compressor topic.
os.environ['COMPRESSOR_TOPIC'] = "zlib"

# Use SQLite infrastructure.
os.environ['INFRASTRUCTURE_FACTORY'] = 'eventsourcing.sqlite:Factory'
os.environ['SQLITE_DBNAME'] = ':memory:'  # Or path to a file on disk.
os.environ['DO_CREATE_TABLE'] = 'y'
```

Run the code in "production" environment.

```python
# Construct an application object.
app = Application()

# Run the test.
test(app)

# Records are encrypted (values not visible in stored data).
assert count_visible_values(app) == 0
```

Configure "production" environment using Postgres infrastructure.

```python
import os

from eventsourcing.cipher import AESCipher

# Generate a cipher key (keep this safe).
cipher_key = AESCipher.create_key(num_bytes=32)

# Cipher key.
os.environ['CIPHER_KEY'] = cipher_key
# Cipher topic.
os.environ['CIPHER_TOPIC'] = "eventsourcing.cipher:AESCipher"
# Compressor topic.
os.environ['COMPRESSOR_TOPIC'] = "zlib"

# Use Postgres infrastructure.
os.environ['INFRASTRUCTURE_FACTORY'] = (
    'eventsourcing.postgresrecorders:Factory'
)
os.environ["POSTGRES_DBNAME"] = "eventsourcing"
os.environ["POSTGRES_HOST"] = "127.0.0.1"
os.environ["POSTGRES_USER"] = "eventsourcing"
os.environ["POSTGRES_PASSWORD"] = "eventsourcing"

# Assume database already created.
os.environ['DO_CREATE_TABLE'] = 'n'
```


## Project

This project is [hosted on GitHub](https://github.com/johnbywater/eventsourcing).
