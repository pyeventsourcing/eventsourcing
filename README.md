[![Coverage Status](https://coveralls.io/repos/github/pyeventsourcing/eventsourcing/badge.svg?branch=main)](https://coveralls.io/github/pyeventsourcing/eventsourcing?branch=main)
[![Documentation Status](https://readthedocs.org/projects/eventsourcing/badge/?version=stable)](https://eventsourcing.readthedocs.io/en/stable/)
[![Latest Release](https://badge.fury.io/py/eventsourcing.svg)](https://pypi.org/project/eventsourcing/)
[![Downloads](https://static.pepy.tech/personalized-badge/eventsourcing?period=total&units=international_system&left_color=grey&right_color=brightgreen&left_text=downloads)](https://pypistats.org/packages/eventsourcing)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


# Event Sourcing in Python

This project is a comprehensive Python library for implementing event sourcing, a design pattern where all
changes to application state are stored as a sequence of events. This library provides a solid foundation
for building event-sourced applications in Python, with a focus on reliability, performance, and developer
experience. Please [read the docs](https://eventsourcing.readthedocs.io/). See also [extension projects](https://github.com/pyeventsourcing).

*"totally amazing and a pleasure to use"*

*"very clean and intuitive"*

*"a huge help and time saver"*

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/pyeventsourcing/eventsourcing)


## Installation

Add the Python `eventsourcing` package to your project. Run `uv init` to start a new project.

    uv add "eventsourcing[pydantic,postgres,umadb]~=10.0.0a3"

Alternatively, install directly into a Python virtual environment from the [Python Package Index](https://pypi.org/project/eventsourcing/10.0.0a3/).
We recommended installing version 10 with the optional extras `pydantic`, `postgres`, `umadb`.

* `pydantic` - modeling events with [Pydantic](https://pydantic.dev/docs/validation/latest/get-started).
* `postgres` - storing events in [PostgreSQL](https://www.postgresql.org).
* `umadb` - storing events in [UmaDB](https://umadb.io).

You can start the UmaDB server with `uv run umadb`.


## Introduction

Version 10 of this library still supports traditional event-sourced aggregates. In these
examples we have chosen to foreground the library's support for DCB, to showcase the
new official support for modeling and serialising events with Pydantic, and to demonstrate
the capabilities of UmaDB.

### Modeling events

Version 10 of this library introduces a new design for modeling events. Pure business attributes
are modeled as "decision" objects. Decision objects are carried within "envelopes" that hold context attributes.
 In previous versions of this library, these concerns were mixed
in a "domain event" class.

The `eventsourcing.pydantic.Decision` class works with the library's Pydantic transcoder, and
provides strong type safety, complex model validation, and fast serialisation. Pydantic is very popular and
widely used, and is a great choice for modeling events in Python.

Equivalent support for [MessagePack](https://msgpack.org) and Python data classes are provided by the `eventsourcing.msgspec`
and `eventsourcing.dataclasses` packages. To enable support for MessagePack, you will need to install
with the `msgspec` optional extra.

Continuing the "dog school" example from previous versions of this library, here are two Pydantic "decision" classes.
One for registering a dog's name, and one for adding new tricks.

```python
from eventsourcing.pydantic import Decision

class DogRegistered(Decision):
    dog_id: str
    name: str

class TrickAdded(Decision):
    dog_id: str
    trick: str
```


### Enduring objects

The `eventsourcing.pydantic.EnduringObject` class works with the `Decision` class
and provides an aggregate-like developer experience. With the support provided by
this library for dynamic consistency boundaries, you can write aggregate-like enduring
objects, and because they use an independent event model, you can refactor your domain
model from being implemented with enduring objects to being implemented with vertical
slices.

Similarly, you can implement your domain model with vertical slices, and then refactor
into enduring objects. You can also mix and match, according to what feels best in your
situation. The underlying event model doesn't need to change.

Let's start by writing an enduring object that supports registering a dog with a dog school,
adding tricks, and reconstructing current state from the history of events.

```python
from eventsourcing.domain import event
from eventsourcing.pydantic import EnduringObject


class Dog(EnduringObject):
    @event(DogRegistered)
    def __init__(self, name: str) -> None:
        self.name = name
        self.tricks: list[str] = []

    @event(TrickAdded)
    def add_trick(self, trick: str) -> None:
        self.tricks.append(trick)
```

### Applications

Let's also define an application class that encapsulates the `Dog` object and introduces some
persistence infrastructure so that our enduring object can be durable.

In this example, the commands and queries are defined with object methods. If you prefer, you
can define module-level functions that have an application object argument, or alternatively
define equivalent command handler and query handler classes.

The `eventsourcing.pydantic.DcbApplication` class works with the Pydantic `EnduringObject` and
`Decision` classes. The `save()` and `get()` methods of the application's repository are
designed to work with enduring objects. One collects and stores new events, the other
reconstructs an enduring object from stored events.

In this example, the application methods `register_dog()`, `add_trick()`, and `get_dog()` can be easily
used by interfaces and integration tests.

```python
from typing import TypedDict

from eventsourcing.pydantic import DcbApplication


class DogSummary(TypedDict):
    name: str
    tricks: tuple[str, ...]


class DogSchool(DcbApplication):
    def register_dog(self, name: str) -> str:
        dog = Dog(name=name)
        self.repository.save(dog)
        return dog.id

    def add_trick(self, dog_id: str, trick: str) -> None:
        dog = self.repository.get(dog_id, Dog)
        dog.add_trick(trick)
        self.repository.save(dog)

    def get_dog(self, dog_id: str) -> DogSummary:
        dog = self.repository.get(dog_id, Dog)
        return {'name': dog.name, 'tricks': tuple(dog.tricks)}
```

### Vertical slices

We can see the `Dog` enduring object class supports three separate use cases.
Registering a new dog, adding a trick, and reconstructing current
state, are all supported by the same highly coherent aggregate-like object class.

Whilst it's nice to keep everything together in one place like this, in some cases
the accumulation of support for many different use cases can be overwhelming. An
alternative style, and your escape hatch, is vertical slices.

In this example, we can separate support for the three use cases into separate "slices". Each
slice can be purely focussed on the needs of the use case it supports. For each use case,
we can define its parameters, a consistency boundary, a projection, and an `execute()`
method or "decider" that triggers a new event.

The `eventsourcing.pydantic.Slice` class works with the `Decision` class and makes it easy
to express the four aspects of a slice in a standard and coherent way:

1. Use case parameters are expressed as constructor params.
2. Consistency boundary expressed with types and tags.
3. Projection defined using the @event decorator.
4. Decider implemented with command-pattern execute() method.

In this example, the three use cases are implemented as `RegisterDog`, `AddTrick` and `DogView`.

```python
from uuid import uuid4

from eventsourcing.pydantic import Selector, Slice


class RegisterDog(Slice):
    # 1. Use case parameters expressed as constructor params.
    def __init__(self, name: str) -> None:
        self.dog_id = f"dog-{uuid4()!s}"
        self.name = name
        self.was_registered = False

    # 2. Consistency boundary expressed with types and tags.
    def consistency_boundary(self) -> Selector:
        return Selector(types=[DogRegistered], tags=[self.dog_id])

    # 3. Projection defined using the @event decorator.
    @event(DogRegistered)
    def _(self) -> None:
        self.was_registered = True

    # 4. Decider implemented with command-pattern execute() method.
    def execute(self) -> None:
        assert not self.was_registered
        self.trigger_event(
            DogRegistered,
            [self.dog_id],
            dog_id=self.dog_id,
            name=self.name,
        )


class AddTrick(Slice):
    # 1. Use case parameters expressed as constructor params.
    def __init__(self, dog_id: str, trick: str) -> None:
        self.dog_id = dog_id
        self.new_trick = trick
        self.was_registered = False

    # 2. Consistency boundary expressed with types and tags.
    def consistency_boundary(self) -> Selector:
        return Selector(types=[DogRegistered], tags=[self.dog_id])

    # 3. Projection defined using the @event decorator.
    @event(DogRegistered)
    def _(self, dog_id: str) -> None:
        assert dog_id == self.dog_id
        self.was_registered = True

    # 4. Decider implemented with command-pattern execute() method.
    def execute(self) -> None:
        assert self.was_registered
        self.trigger_event(
            TrickAdded,
            [self.dog_id],
            dog_id=self.dog_id,
            trick=self.new_trick,
        )


class DogView(Slice):
    # 1. Use case parameters expressed as constructor params.
    def __init__(self, dog_id: str) -> None:
        self.dog_id = dog_id
        self.name = ""
        self.tricks: list[str] = []

    # 2. Consistency boundary expressed with types and tags.
    def consistency_boundary(self) -> Selector:
        return Selector(types=self.projected_types, tags=[self.dog_id])

    # 3. Projection defined using the @event decorator.
    @event(DogRegistered)
    def _(self, dog_id: str, name: str) -> None:
        assert dog_id == self.dog_id
        self.was_registered = True
        self.name = name

    @event(TrickAdded)
    def _(self, trick: str) -> None:
        self.tricks.append(trick)

    # 4. No execute() method - views don't need to trigger events.
```

As we did for the `Dog` object above, let's also define an application class that encapsulates the
slices and persistence infrastructure, presenting an API that can be used from tests and interfaces.

The `eventsourcing.pydantic.DcbApplication` class also works with the `Slice` class
and provides a `do()` method especially for vertical slices.

```python
class DogSchoolWithSlices(DcbApplication):
    def register_dog(self, name: str) -> str:
        return self.do(RegisterDog(name=name)).dog_id

    def add_trick(self, dog_id: str, trick: str) -> None:
        self.do(AddTrick(dog_id=dog_id, trick=trick))

    def get_dog(self, dog_id: str) -> DogSummary:
        dog = self.do(DogView(dog_id))
        return {'name': dog.name, 'tricks': tuple(dog.tricks)}
```

### Tests and interfaces

The integration test `test_dog_school()` exercises the command and query methods
defined on the DCB applications. Since `DogSchool` and `DogSchoolWithSlices` present
the same API, they can be exercised in the same way. You can see the enduring object
and the slices generated exactly the same recorded events. This means an application
can be refactored from using enduring objects to being implemented with vertical
slices, and vice versa.

```python
from datetime import datetime
from uuid import UUID

from eventsourcing.domain import put_metadata_in_context


def test_dog_school(
    cls: type[DogSchool | DogSchoolWithSlices],
    env: dict[str, str] | None,
    label: str,
) -> None:
    print(f"Running test for: {label}")
    started = datetime.now()

    app = cls(env=env)

    # Get current max sequence position.
    head = app.events.recorder.head()

    # Context attributes become event metadata.
    context_attributes = {"user_id": "user-123"}
    with put_metadata_in_context(context_attributes):

        # Evolve application state.
        dog_id = app.register_dog('Fido')
        app.add_trick(dog_id, 'roll over')
        app.add_trick(dog_id, 'play dead')

    # Query application state.
    dog = app.get_dog(dog_id)
    assert dog['name'] == 'Fido'
    assert dog['tricks'] == ('roll over', 'play dead')

    # Read all events.
    events = list(app.events.read(after=head))
    assert len(events) == 3

    # Check the event decisions.
    print(f"Dog ID: {dog_id}")
    assert isinstance(events[0].decision, DogRegistered)
    assert isinstance(events[1].decision, TrickAdded)
    assert isinstance(events[2].decision, TrickAdded)
    assert events[0].decision.dog_id == dog_id
    assert events[0].decision.name == 'Fido'
    assert events[1].decision.dog_id == dog_id
    assert events[1].decision.trick == 'roll over'
    assert events[2].decision.dog_id == dog_id
    assert events[2].decision.trick == 'play dead'

    # Check the event envelopes.
    assert events[0].uuid != events[1].uuid
    assert events[1].uuid != events[2].uuid
    assert events[0].metadata == context_attributes
    assert events[1].metadata == context_attributes
    assert events[2].metadata == context_attributes
    assert events[0].tags == [dog_id]
    assert events[1].tags == [dog_id]
    assert events[2].tags == [dog_id]

    # Print duration.
    duration = (datetime.now() - started).total_seconds()
    print(f"Duration: {(duration*1000):.2f}ms")
    print()
```

Because the application class is defined independently of persistence infrastructure,
we can run the test in memory, with Postgres, and with UmaDB.

Let's run the applications in memory.

```python
test_dog_school(
    cls=DogSchool,
    env=None,
    label="Enduring object in memory"
)

test_dog_school(
    cls=DogSchoolWithSlices,
    env=None,
    label="Slices in memory"
)
```

Now, let's run the applications with Postgres. To run with Postgres,
you need to install and start Postgres, create a database and a user,
and configure the application environment in the following way.

```python
postgres_env: dict[str, str] = {
    "PERSISTENCE_MODULE": 'eventsourcing.dcb.postgres_tt',
    "POSTGRES_DBNAME": "eventsourcing",
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "5432",
    "POSTGRES_USER": "eventsourcing",
    "POSTGRES_PASSWORD": "eventsourcing",
}

test_dog_school(
    cls=DogSchool,
    env=postgres_env,
    label="Enduring object with Postgres"
)

test_dog_school(
    cls=DogSchoolWithSlices,
    env=postgres_env,
    label="Slice with Postgres"
)
```

Finally, let's run the applications with UmaDB. To run with UmaDB,
you need to install the Python package `eventsourcing_umadb`, run
the installed `umadb` server binary, and configure the application
environment in the following way.

```python
umadb_env: dict[str, str] = {
    "PERSISTENCE_MODULE": 'eventsourcing_umadb',
    "UMADB_URI": 'http://localhost:50051',
}

test_dog_school(
    cls=DogSchool,
    env=umadb_env,
    label="Enduring object with UmaDB"
)

test_dog_school(
    cls=DogSchoolWithSlices,
    env=umadb_env,
    label="Slices with UmaDB"
)
```

### Performance results

By matching the consistency boundary to the needs of the use case,
application commands can execute faster. Needless conflicts
can also be avoided. The table below shows duration times for
the tests above.

| test                            | duration |
|---------------------------------|----------|
| Enduring Object - In memory     |  0.68ms  |
| Vertical Slices - In memory     |  0.38ms  |
| Enduring Object - With Postgres |  44.65ms |
| Vertical Slices - With Postgres |  28.25ms |
| Enduring Object - With UmaDB    |  6.22ms  |
| Vertical Slices - With UmaDB    |  2.62ms  |


### Read the docs

Please read the [documentation](https://eventsourcing.readthedocs.io/) for more information.


## Features

**Flexible event store** — flexible persistence of domain events. Combines
an event mapper and an event recorder in ways that can be easily extended.
Mapper uses a transcoder that can be easily substituted or extended to support
custom model object types. Recorders supporting different databases can be easily
substituted and configured with environment variables.

**Domain models and applications** — base classes for event-sourced domain models
and applications. Suggests how to structure an event-sourced application. This
library supports event-sourced aggregates and dynamic consistency boundaries.

**Application-level encryption and compression** — encrypts and decrypts events inside the
application. This means data will be encrypted in transit across a network ("on the wire")
and at disk level including backups ("at rest"), which is a legal requirement in some
jurisdictions when dealing with personally identifiable information (PII) for example
the EU's GDPR. Compression reduces the size of stored domain events and snapshots, usually
by around 25% to 50% of the original size. Compression reduces the size of data
in the database and decreases transit time across a network.

**Snapshotting** — reduces access-time for aggregates with many domain events.

**Versioning** - allows domain model changes to be introduced after an application
has been deployed. Both domain events and aggregate classes can be versioned.
The recorded state of an older version can be upcast to be compatible with a new
version. Stored events and snapshots are upcast from older versions
to new versions before the event or aggregate object is reconstructed.

**Optimistic concurrency control** — ensures a distributed or horizontally scaled
application doesn't become inconsistent due to concurrent method execution. Leverages
optimistic concurrency controls in adapted database management systems.

**Notifications and projections** — reliable propagation of application
events with pull-based notifications allows the application state to be
projected accurately into replicas, indexes, view models, and other applications.
Supports materialised views and CQRS.

**Event-driven systems** — reliable event processing. Event-driven systems
can be defined independently of particular persistence infrastructure and mode of
running.

**Detailed documentation** — documentation provides general overview, introduction
of concepts, explanation of usage, and detailed descriptions of library classes.
All code is annotated with type hints.

**Worked examples** — includes examples showing how to develop aggregates, applications
and systems.



## Extensions

The GitHub organisation
[Event Sourcing in Python](https://github.com/pyeventsourcing)
hosts extension projects for the Python eventsourcing library.
There are projects that adapt popular ORMs such as
[Django](https://github.com/pyeventsourcing/eventsourcing-django#readme)
and [SQLAlchemy](https://github.com/pyeventsourcing/eventsourcing-sqlalchemy#readme).
There are projects that adapt specialist event stores such as
[Axon Server](https://github.com/pyeventsourcing/eventsourcing-axonserver#readme),
[KurrentDB](https://github.com/pyeventsourcing/eventsourcing-kurrentdb#readme),
and [UmaDB](https://github.com/pyeventsourcing/eventsourcing-umadb#readme).
There are projects that support popular NoSQL databases such as
[DynamoDB](https://github.com/pyeventsourcing/eventsourcing-dynamodb#readme).
There are also projects that provide examples of using the
library with web frameworks such as
[FastAPI](https://github.com/pyeventsourcing/example-fastapi#readme)
and [Flask](https://github.com/pyeventsourcing/example-flask#readme),
and for serving applications and running systems with efficient
inter-process communication technologies like [gRPC](https://github.com/pyeventsourcing/eventsourcing-grpc#readme).
And there are examples of event-sourced applications and systems
of event-sourced applications, such as the
[Paxos system](https://github.com/pyeventsourcing/example-paxos#readme),
which is used as the basis for a
[replicated state machine](https://github.com/pyeventsourcing/example-paxos/tree/master/replicatedstatemachine),
which is used as the basis for a
[distributed key-value store](https://github.com/pyeventsourcing/example-paxos/tree/master/keyvaluestore).

## Project

This project is [hosted on GitHub](https://github.com/pyeventsourcing/eventsourcing).

Please register questions, requests and
[issues on GitHub](https://github.com/pyeventsourcing/eventsourcing/issues),
or post in the project's Slack channel.

There is a [Discord server](https://discord.gg/C8TVRdN9K5)
for this project, which you are [welcome to join](https://discord.gg/C8TVRdN9K5).

Please refer to the [documentation](https://eventsourcing.readthedocs.io/) for installation and usage guides.

