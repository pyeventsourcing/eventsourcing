[![Build Status](https://github.com/johnbywater/eventsourcing/actions/workflows/runtests.yaml/badge.svg?branch=9.0)](https://github.com/johnbywater/eventsourcing/tree/9.0)
[![Coverage Status](https://coveralls.io/repos/github/johnbywater/eventsourcing/badge.svg?branch=9.0)](https://coveralls.io/github/johnbywater/eventsourcing?branch=9.0)
[![Documentation Status](https://readthedocs.org/projects/eventsourcing/badge/?version=v9.0.3)](https://eventsourcing.readthedocs.io/en/v9.0.3/)
[![Latest Release](https://badge.fury.io/py/eventsourcing.svg)](https://pypi.org/project/eventsourcing/)


# Event Sourcing in Python

A library for event sourcing in Python.

*"totally amazing and a pleasure to use"*

[Read the documentation here](https://eventsourcing.readthedocs.io/).


## Installation

Use pip to install the [stable distribution](https://pypi.org/project/eventsourcing/)
from the Python Package Index. Please note, it is recommended to
install Python packages into a Python virtual environment.

    $ pip install eventsourcing


## Synopsis

Use the library's `Aggregate` base class and `@event` decorator to define
event-sourced aggregates.

Derive your aggregate classes from the `Aggregate`
base class. Create new aggregate instances by calling the derived
aggregate class. Use the `@event` decorator to define aggregate event
classes. Events will be triggered when decorated methods are called.

```python
from eventsourcing.domain import Aggregate, event


class World(Aggregate):
    @event('Created')
    def __init__(self, name: str) -> None:
        self.name = name
        self.history = ()

    @event('SomethingHappened')
    def make_it_so(self, what: str) -> None:
        self.history += (what,)
```

Use the library's `Application` class to define an event-sourced application.
Applications store and retrieve aggregates, using a persistence mechanism for
aggregate events.

Derive your application classes from the `Application` base class. Add command
and query methods to manipulate and access the state of the application.

```python
from typing import Tuple
from uuid import UUID

from eventsourcing.application import Application


class Universe(Application):
    def create_world(self, name: str) -> UUID:
        world = World(name)
        self.save(world)
        return world.id

    def make_it_so(self, world_id: UUID, what: str) -> None:
        world = self._get_world(world_id)
        world.make_it_so(what)
        self.save(world)

    def get_history(self, world_id) -> Tuple:
        return self._get_world(world_id).history

    def _get_world(self, world_id) -> World:
        world = self.repository.get(world_id)
        assert isinstance(world, World)
        return world

```

Construct an instance of the application by calling the application class.

```python
application = Universe()

```

Create a new aggregate by calling the application method `create_world()`.

```python
world_id = application.create_world('Earth')
```

Evolve the state of the application's aggregate by calling the
application command method `make_it_so()`.

```python
application.make_it_so(world_id, 'dinosaurs')
application.make_it_so(world_id, 'trucks')
application.make_it_so(world_id, 'internet')

```

Access the state of the application's aggregate by calling the
application query method `get_history()`.

```python
history = application.get_history(world_id)
assert history == ('dinosaurs', 'trucks', 'internet')
```

See the discussion below and the library's
[documentation](https://eventsourcing.readthedocs.io/)
for more information.

## Features

**Aggregates and applications** — base classes for event-sourced aggregates
and applications. Suggests how to structure an event-sourced application. All
classes are fully type-hinted to guide developers in using the library.

**Flexible event store** — flexible persistence of aggregate events. Combines
an event mapper and an event recorder in ways that can be easily extended.
Mapper uses a transcoder that can be easily extended to support custom
model object types. Recorders supporting different databases can be easily
substituted and configured with environment variables.

**Application-level encryption and compression** — encrypts and decrypts events inside the
application. This means data will be encrypted in transit across a network ("on the wire")
and at disk level including backups ("at rest"), which is a legal requirement in some
jurisdictions when dealing with personally identifiable information (PII) for example
the EU's GDPR. Compression reduces the size of stored aggregate events and snapshots, usually
by around 25% to 50% of the original size. Compression reduces the size of data
in the database and decreases transit time across a network.

**Snapshotting** — reduces access-time for aggregates that have many events.

**Versioning** - allows changes to be introduced after an application
has been deployed. Both aggregate events and aggregate snapshots can be versioned.

**Optimistic concurrency control** — ensures a distributed or horizontally scaled
application doesn't become inconsistent due to concurrent method execution. Leverages
optimistic concurrency controls in adapted database management systems.

**Notifications and projections** — reliable propagation of application
events with pull-based notifications allows the application state to be
projected accurately into replicas, indexes, view models, and other applications.
Supports materialized views and CQRS.

**Event-driven systems** — reliable event processing. Event-driven systems
can be defined independently of particular persistence infrastructure and mode of
running.

**Detailed documentation** — documentation provides general overview, introduction
of concepts, explanation of usage, and detailed descriptions of library classes.

**Worked examples** — includes examples showing how to develop aggregates, applications
and systems.


## Aggregates

The example above shows an event-sourced aggregate class named
`World`. Its ``__init__()`` method takes a `name` argument which
is used to initialise the `name` attribute, and also initialises
a `history` attribute as an empty tuple. It has a method `make_it_so()`
that takes an argument `what` and appends the given value to the
`history` of the `World`.

The `World` class uses the aggregate base class `Aggregate` from
the library's `domain` module. It uses the `@event` decorator to
define two aggregate event classes, `Created` and `SomethingHappened`.
The attributes of the event classes match the parameters of the
decorated method signature.

Calling the `World` aggregate class will construct a new aggregate instance.

```python
# Call the aggregate class to create a new aggregate object.
world = World(name='Earth')

# Check the name of the new aggregate object.
assert world.name == 'Earth'

# Check the state of the new aggregate object.
assert world.history == ()
```

The `World` aggregate object has an `id` attribute. It is a version 4
universally unique identifier (UUID). This follows from the default
behaviour of the `Aggregate` base class.

```python

# The aggregate has an ID.
assert isinstance(world.id, UUID)
```

Calling the `make_it_so()` command method will change the state of the aggregate.

```python
# Execute aggregate commands.
world.make_it_so('dinosaurs')
world.make_it_so('trucks')
world.make_it_so('internet')

# Check aggregate state.
assert world.history[0] == 'dinosaurs'
assert world.history[1] == 'trucks'
assert world.history[2] == 'internet'
```

How does it work? When the aggregate class is called, a `Created` event class
is constructed. This event object instance is used to construct an instance
of the `World` aggregate class. The `Created` event class is defined with an
attribute `name`. The event object instance will have the value of the `name`
argument given when calling the aggregate class. After the aggregate object
is instantiated, the event object is appended to an internal list of pending
events. The `World` object is then returned to the caller.

Similarly, when the command method `make_it_so()` is called on an instance of
the `World` class, a `SomethingHappened` event is constructed. The
`SomethingHappened` event object class is defined with an attribute `what`.
The event object instance will have the value of the `what` argument given
when calling the command method. This event object is used to evolve the
state of the aggregate object, using the body of the decorated method.
Hence, the value `what` is appended to the `history` of the `World`
aggregate instance. After the `SomethingHappened` event is applied to the
aggregate, the event will be immediately appended to the aggregate's internal
list of pending events.

Pending event objects can be collected using the aggregate's `collect_events()`
method. The aggregate event classes are defined on the aggregate class, so that
they are "namespaced" within the aggregate class. Hence, the "fully qualified"
name of the `Created` event is `World.Created`. And the "fully qualified" name
of the `SomethingHappened` event is `World.SomethingHappened`.

```python
# Collect events.
events = world.collect_events()
assert len(events) == 4

assert type(events[0]).__name__ == 'Created'
assert type(events[1]).__name__ == 'SomethingHappened'
assert type(events[2]).__name__ == 'SomethingHappened'
assert type(events[3]).__name__ == 'SomethingHappened'

assert type(events[0]).__qualname__ == 'World.Created'
assert type(events[1]).__qualname__ == 'World.SomethingHappened'
assert type(events[2]).__qualname__ == 'World.SomethingHappened'
assert type(events[3]).__qualname__ == 'World.SomethingHappened'
```

Collecting and storing aggregate events and reconstructing aggregates
from stored events are responsibilities of the library's `Application`
class. The `collect_events()` method is used by the application's
`save()` method to collect aggregate events, so the event objects can
be stored in a database. You probably won't need to call this method
explicitly in your project code.

The collected event objects can be used to reconstruct the state of
the aggregate. The application repository's `get()` method
reconstructs aggregates from stored events in this way (see below).

```python
copy = None
for event in events:
    copy = event.mutate(copy)

assert copy.history == world.history
assert copy.id == world.id
assert copy.version == world.version
assert copy.created_on == world.created_on
assert copy.modified_on == world.modified_on
```

Please note, the body of a method decorated with the `@event` decorator
will be executed each time the associated event is applied to evolve
the state of the aggregate, both just after triggering the event and
each time when reconstructing aggregates from stored events. For this
reason, the body of the decorated method should return the Python value
`None`. It is normal for command methods to return `None`. However, if
you do need to return values from your aggregate command methods, then
define a command method that is not decorated with the `@event` decorator,
and return the value from the non-decorated method after calling the decorated
method.

Any processing of method arguments that should be done only once, and not
repeated when reconstructing aggregates from stored events, should be done
in the calling method. For example, if the triggered event will have a new
UUID, you will either want to use a separate command method, or create this
value in the expression used when calling the method, and not generate the
UUID in the decorated method body. Otherwise, rather than being fixed in the
stored state of the aggregate, a new UUID will be created each time the aggregate
is reconstructed. See the library's
[domain module documentation](https://eventsourcing.readthedocs.io/)
for more information.

Please also note, if an exception happens to be raised in the decorated method
body, then the triggered event will not be appended to the internal list of
pending events as described above. If you are careful, this behaviour (of not
appending the event to the list of pending events) can be used to validate
the state of the event against the current state of the aggregate. But if
you wish to continue using the same aggregate instance after catching a
validation exception in the caller of the decorated method, please just be
careful to complete all validation before adjusting the state of the aggregate,
otherwise you will need to retrieve a fresh instance from the repository.


## Applications

An "application" object in this library roughly corresponds to a "bounded context"
in Domain-Driven Design. An application can have aggregates of different types in
its domain model.

The example above defines an event-sourced application named
`Universe`. The application class `Universe` uses the
application base class `Application` from the library's
`application` module. When the `Universe` application class is
called, an application object is constructed.

A `Universe` application object has a command
method `create_world()` that creates and saves new instances of
the aggregate class `World`. It has a command method
`make_it_so()` that calls the aggregate command method
`make_it_so()` of an already existing aggregate object. And it
has a query method `get_history()` that returns the `history` of
an aggregate object.

When the application command method `create_world()` is called,
a new `World` aggregate object is created, the new aggregate
object is saved by calling the application's `save()` method,
and then the ID of the aggregate is returned to the caller.

When the application command method `make_it_so()` is called with
the ID of an aggregate, the repository is used to get the
aggregate, the aggregate's `make_it_so()` method is called with
the given value of `what`, and the aggregate is saved by calling
the application's `save()` method.

When the application query method `get_history()` is called with
the ID of an aggregate, the repository is used to get the
aggregate, and the value of the aggregate's `history` attribute
is returned to the caller.

How does it work? The `Application` class provides persistence
infrastructure that can collect, serialise, and store aggregate
events. It can also reconstruct aggregates from stored events.

The application `save()` method saves aggregates by
collecting and storing pending aggregate events. The `save()`
method calls the given aggregate's `collect_events()` method and
puts the pending aggregate events in an event store, with a
guarantee that either all the events will be stored or none of
them will be.

The application `repository` has a `get()`
method that can be used to obtain previously saved aggregates.
The `get()` method is called with an aggregate ID. It retrieves
stored events for an aggregate from an event store, then
reconstructs the aggregate object from its previously stored
events (see above), and then returns the reconstructed aggregate object to
the caller. The application class can be configured using
environment variables to work with different databases, and
optionally to encrypt and compress stored events. By default,
the application serialises aggregate events using JSON, and
stores them in memory as "plain old Python objects". The library
includes support for storing events in SQLite and PosgreSQL (see
below). Other databases are available.

The `Application` class also has a `log` object which can be
used to get all the aggregate events that have been stored
across all the aggregates of an application. The log presents
the aggregate events in the order in which they were stored,
as a sequence of event notifications. Each of the event
notifications has an integer ID which increases along the
sequence. The `log` can be used to propagate the state of
the application in a manner that supports deterministic
processing of the application state in event-driven systems.

```python
log_section = application.log['1,4']
notifications = log_section.items
assert [n.id for n in notifications] == [1, 2, 3, 4]

assert 'World.Created' in notifications[0].topic
assert 'World.SomethingHappened' in notifications[1].topic
assert 'World.SomethingHappened' in notifications[2].topic
assert 'World.SomethingHappened' in notifications[3].topic

assert b'Earth' in notifications[0].state
assert b'dinosaurs' in notifications[1].state
assert b'trucks' in notifications[2].state
assert b'internet' in notifications[3].state

assert world_id == notifications[0].originator_id
assert world_id == notifications[1].originator_id
assert world_id == notifications[2].originator_id
assert world_id == notifications[3].originator_id
```

The `test()` function below demonstrates the example in more detail,
by creating many aggregates in one application, reading event
notifications from the application log, retrieving historical
versions of an aggregate. The optimistic concurrency control
feature, and the compression and encryption features are also
demonstrated.

```python
from eventsourcing.persistence import RecordConflictError
from eventsourcing.system import NotificationLogReader


def test(app: Universe, expect_visible_in_db: bool):

    # Check app has zero event notifications.
    assert len(app.log['1,10'].items) == 0

    # Create a new aggregate.
    world_id = app.create_world('Earth')

    # Execute application commands.
    app.make_it_so(world_id, 'dinosaurs')
    app.make_it_so(world_id, 'trucks')

    # Check recorded state of the aggregate.
    assert app.get_history(world_id) == (
        'dinosaurs',
        'trucks'
    )

    # Execute another command.
    app.make_it_so(world_id, 'internet')

    # Check recorded state of the aggregate.
    assert app.get_history(world_id) == (
        'dinosaurs',
        'trucks',
        'internet'
    )

    # Check values are (or aren't visible) in the database.
    values = [b'dinosaurs', b'trucks', b'internet']
    if expect_visible_in_db:
        expected_num_visible = len(values)
    else:
        expected_num_visible = 0

    actual_num_visible = 0
    reader = NotificationLogReader(app.log)
    for notification in reader.read(start=1):
        for what in values:
            if what in notification.state:
                actual_num_visible += 1
                break
    assert expected_num_visible == actual_num_visible

    # Get historical state (at version 3, before 'internet' happened).
    old = app.repository.get(world_id, version=3)
    assert len(old.history) == 2
    assert old.history[-1] == 'trucks' # last thing to have happened was 'trucks'

    # Check app has four event notifications.
    assert len(app.log['1,10'].items) == 4

    # Optimistic concurrency control (no branches).
    old.make_it_so('future')
    try:
        app.save(old)
    except RecordConflictError:
        pass
    else:
        raise Exception("Shouldn't get here")

    # Check app still has only four event notifications.
    assert len(app.log['1,10'].items) == 4

    # Read event notifications.
    reader = NotificationLogReader(app.log)
    notifications = list(reader.read(start=1))
    assert len(notifications) == 4

    # Create eight more aggregate events.
    world_id = app.create_world('Mars')
    app.make_it_so(world_id, 'plants')
    app.make_it_so(world_id, 'fish')
    app.make_it_so(world_id, 'mammals')

    world_id = app.create_world('Venus')
    app.make_it_so(world_id, 'morning')
    app.make_it_so(world_id, 'afternoon')
    app.make_it_so(world_id, 'evening')

    # Get the new event notifications from the reader.
    last_id = notifications[-1].id
    notifications = list(reader.read(start=last_id + 1))
    assert len(notifications) == 8

    # Get all the event notifications from the application log.
    notifications = list(reader.read(start=1))
    assert len(notifications) == 12
```

This example can be adjusted and extended for any event-sourced application.


## Project structure

You are free to structure your project files however you wish. You
may wish to put your aggregate classes in a file named
`domainmodel.py` and your application class in a file named
`application.py`.

    myproject/
    myproject/application.py
    myproject/domainmodel.py
    myproject/tests.py

But you can start by first writing a failing test in `tests.py`, then define
your application and aggregate classes in the test module, and then refactor
by moving things to separate Python modules.


## Development environment

We can run the code in default "development" environment using
the default "Plain Old Python Object" infrastructure (which keeps
stored events in memory). The example below runs with no compression or
encryption of the stored events.

```python
# Construct an application object.
app = Universe()

# Run the test.
test(app, expect_visible_in_db=True)

```

## SQLite environment

You can configure "production" environment to use the library's
SQLite infrastructure with the following environment variables.
Using SQLite infrastructure will keep stored events in an
SQLite database.

The example below uses zlib and AES to compress and encrypt the stored
events in an SQLite database (but this is optional). To use the library's
encryption functionality, please install the library with the `crypto`
option (or just install the `pycryptodome` package.)

    $ pip install eventsourcing[crypto]

An in-memory SQLite database is used in this example. To store your events on
disk, use a file path as the value of the `SQLITE_DBNAME` environment variable.

```python
import os

from eventsourcing.cipher import AESCipher

# Generate a cipher key (keep this safe).
cipher_key = AESCipher.create_key(num_bytes=32)

# Cipher key.
os.environ['CIPHER_KEY'] = cipher_key
# Cipher topic.
os.environ['CIPHER_TOPIC'] = 'eventsourcing.cipher:AESCipher'
# Compressor topic.
os.environ['COMPRESSOR_TOPIC'] = 'eventsourcing.compressor:ZlibCompressor'

# Use SQLite infrastructure.
os.environ['INFRASTRUCTURE_FACTORY'] = 'eventsourcing.sqlite:Factory'
os.environ['SQLITE_DBNAME'] = ':memory:'  # Or path to a file on disk.
```

Having configured the application with these environment variables, we
can construct the application and run the test using SQLite.

```python
# Construct an application object.
app = Universe()

# Run the test.
test(app, expect_visible_in_db=False)
```

## PostgreSQL environment

You can configure "production" environment to use the library's
PostgresSQL infrastructure with the following environment variables.
Using PostgresSQL infrastructure will keep stored events in a
PostgresSQL database.

Please note, to use the library's PostgreSQL functionality,
please install the library with the `postgres` option (or just
install the `psycopg2` package.)

    $ pip install eventsourcing[postgres]

Please note, the library option `postgres_dev` will install the
`psycopg2-binary` which is much faster, but this is not recommended
for production use. The binary package is a practical choice for
development and testing but in production it is advised to use
the package built from sources.

The example below also uses zlib and AES to compress and encrypt the
stored events (but this is optional). To use the library's
encryption functionality with PostgreSQL, please install the library
with both the `crypto` and the `postgres` option (or just install the
`pycryptodome` and `psycopg2` packages.)

    $ pip install eventsourcing[crypto,postgres]


It is assumed for this example that the database and database user have
already been created, and the database server is running locally.

```python
import os

from eventsourcing.cipher import AESCipher

# Generate a cipher key (keep this safe).
cipher_key = AESCipher.create_key(num_bytes=32)

# Cipher key.
os.environ['CIPHER_KEY'] = cipher_key
# Cipher topic.
os.environ['CIPHER_TOPIC'] = 'eventsourcing.cipher:AESCipher'
# Compressor topic.
os.environ['COMPRESSOR_TOPIC'] = 'eventsourcing.compressor:ZlibCompressor'

# Use Postgres infrastructure.
os.environ['INFRASTRUCTURE_FACTORY'] = 'eventsourcing.postgres:Factory'
os.environ['POSTGRES_DBNAME'] = 'eventsourcing'
os.environ['POSTGRES_HOST'] = '127.0.0.1'
os.environ['POSTGRES_PORT'] = '5432'
os.environ['POSTGRES_USER'] = 'eventsourcing'
os.environ['POSTGRES_PASSWORD'] = 'eventsourcing'
```

Having configured the application with these environment variables,
we can construct the application and run the test using PostgreSQL.


```python
# Construct an application object.
app = Universe()

# Run the test.
test(app, expect_visible_in_db=False)
```

## Extensions

The GitHub organisation
[Event Sourcing in Python](https://github.com/pyeventsourcing)
hosts extension projects for the Python eventsourcing library.
These projects aim to provide functionality supported by v8
of this library that was put out of scope in v9. There are
projects that support ORMs such as Django and SQLAlchemy.
There are database projects supporting AxonDB, DynamoDB,
EventStoreDB, and Apache Kafka. Other projects support
alternatives to the library defaults, such as transcoding
of domain events with Protocol Buffers rather than JSON.
There are also projects that provide examples of using the
library with such things as FastAPI, Flask, and serverless.

## Project

This project is [hosted on GitHub](https://github.com/johnbywater/eventsourcing).

Please register questions, requests and
[issues on GitHub](https://github.com/johnbywater/eventsourcing/issues),
or post in the project's Slack channel.

There is a [Slack channel](https://join.slack.com/t/eventsourcinginpython/shared_invite/enQtMjczNTc2MzcxNDI0LTJjMmJjYTc3ODQ3M2YwOTMwMDJlODJkMjk3ZmE1MGYyZDM4MjIxODZmYmVkZmJkODRhZDg5N2MwZjk1YzU3NmY)
for this project, which you are [welcome to join](https://join.slack.com/t/eventsourcinginpython/shared_invite/enQtMjczNTc2MzcxNDI0LTJjMmJjYTc3ODQ3M2YwOTMwMDJlODJkMjk3ZmE1MGYyZDM4MjIxODZmYmVkZmJkODRhZDg5N2MwZjk1YzU3NmY).

Please refer to the [documentation](https://eventsourcing.readthedocs.io/) for installation and usage guides.
