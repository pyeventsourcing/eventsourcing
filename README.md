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

Add the Python `eventsourcing` package to your project, or install into a Python virtual
environment from the [Python Package Index](https://pypi.org/project/eventsourcing/). We recommended installing with the
`pydantic` option to enable the library's support for Pydantic.

    $ pip install eventsourcing[pydantic]~=10.0.0


## Synopsis

Version 10 of this library still supports traditional event-sourced aggregates. However,
we have chosen to foreground the library's support for DCB, and to showcase the new
official support for modeling and serialising events with Pydantic.

### Modeling events

Version 10 of this library introduces a new design for modeling events. Pure business attributes
are modeled as "decision" objects. Decision objects are carried within "envelopes" that hold context attributes.

The `PydanticDecision` class works with the library's Pydantic transcoder, and
provides strong type safety, complex model validation, and fast serialisation. Pydantic is very popular and
widely used, and is a great choice for modeling events in Python.

Continuing the "dog school" example from previous versions, the example below defines two "decision" classes, one for registering a dog's name, and one for adding new tricks.

```python
from eventsourcing.pydantic.immutable import PydanticDecision

class DogRegistered(PydanticDecision):
    dog_id: str
    name: str

class TrickAdded(PydanticDecision):
    trick: str

```


### Enduring objects

With dynamic consistency boundaries, you can write aggregate-like entities, which are called "enduring objects" in
this library. You can refactor the enduring object into vertical slices. Similarly, you can define your domain model
with vertical slices, and then refactor into enduring objects. You can also mix and match, according to what feels
best in your situation.

```python
from eventsourcing.pydantic.mutable import PydanticEnduringObject
from eventsourcing.domain import event


class Dog(PydanticEnduringObject):
    @event(DogRegistered)
    def __init__(self, dog_id: str, name: str) -> None:
        self.dog_id = dog_id
        self.name = name
        self.tricks: list[str] = []

    @event(TrickAdded)
    def add_trick(self, trick: str) -> None:
        self.tricks.append(trick)
```

Let's also define an application class that encapsulates the `Dog` object and persistence infrastructure so
that our enduring object is actually durable.

The application methods `register_dog()`, `add_trick()`, and `get_dog()` can be easily used by interfaces and tests.

```python
from typing import Any
from uuid import uuid4

from eventsourcing.pydantic.application import PydanticDCBApplication


class DogSchoolWithEnduringObjects(PydanticDCBApplication):
    def register_dog(self, name: str) -> str:
        dog = Dog(dog_id=str(uuid4()), name=name)
        self.repository.save(dog)
        return dog.dog_id

    def add_trick(self, dog_id: str, trick: str) -> None:
        dog = self.repository.get(dog_id, Dog)
        dog.add_trick(trick)
        self.repository.save(dog)

    def get_dog(self, dog_id: str) -> dict[str, Any]:
        dog = self.repository.get(dog_id, Dog)
        return {'name': dog.name, 'tricks': tuple(dog.tricks)}
```

### Vertical slices

The `Dog` object above really combines support for three separate use cases: registering a new dog, adding a trick,
and reconstructing the current state of the dog from the history of events.

We can split these three concerns into separate "slices" that are purely focussed on only the needs of each use case.
For each use case we can define its parameters, a consistency boundary, a projection, and an `execute()` method that
will trigger a new event.

```python
from eventsourcing.pydantic.mutable import PydanticEnduringObject, PydanticSlice
from eventsourcing.domain import event, Selector


class RegisterDog(PydanticSlice):
    def __init__(self, dog_id: str, name: str) -> None:
        self.dog_id = dog_id
        self.name = name
        self.was_registered = False

    def consistency_boundary(
        self,
    ) -> Selector[PydanticDecision]:
        return Selector(types=[DogRegistered], tags=[self.dog_id])

    @event(DogRegistered)
    def _(self) -> None:
        self.was_registered = True

    def execute(self) -> None:
        assert not self.was_registered
        self.trigger_event(
            DogRegistered,
            tags=[self.dog_id],
            dog_id=self.dog_id,
            name=self.name,
        )


class AddTrick(PydanticSlice):
    def __init__(self, dog_id: str, trick: str) -> None:
        self.dog_id = dog_id
        self.new_trick = trick
        self.was_registered = False
        self.tricks: list[str] = []

    def consistency_boundary(
        self,
    ) -> Selector[PydanticDecision]:
        return Selector(types=[DogRegistered, TrickAdded], tags=[self.dog_id])

    @event(DogRegistered)
    def _(self, dog_id: str) -> None:
        assert dog_id == self.dog_id
        self.was_registered = True

    @event(TrickAdded)
    def _(self, trick: str) -> None:
        self.tricks.append(trick)

    def execute(self) -> None:
        assert self.was_registered
        assert self.new_trick not in self.tricks
        self.trigger_event(
            TrickAdded,
            tags=[self.dog_id],
            trick=self.new_trick,
        )

class DogView(PydanticSlice):
    def __init__(self, dog_id: str) -> None:
        self.dog_id = dog_id
        self.name = ""
        self.tricks: list[str] = []

    def consistency_boundary(
        self,
    ) -> Selector[PydanticDecision]:
        return Selector(types=self.projected_types, tags=[self.dog_id])

    @event(DogRegistered)
    def _(self, dog_id: str, name: str) -> None:
        assert dog_id == self.dog_id
        self.was_registered = True
        self.name = name

    @event(TrickAdded)
    def _(self, trick: str) -> None:
        self.tricks.append(trick)
```

Let's also define an application class that encapsulates the slices and persistence infrastructure so
that our enduring object is actually durable.

The application methods `register_dog()`, `add_trick()`, and `get_dog()` can be easily used by interfaces and tests.


```python
from typing import Any
from uuid import uuid4

from eventsourcing.pydantic.application import PydanticDCBApplication


class DogSchoolWithSlices(PydanticDCBApplication):
    def register_dog(self, name: str) -> str:
        dog_id = str(uuid4())
        self.do(RegisterDog(dog_id=dog_id, name=name))
        return dog_id

    def add_trick(self, dog_id: str, trick: str) -> None:
        self.do(AddTrick(dog_id=dog_id, trick=trick))

    def get_dog(self, dog_id: str) -> dict[str, Any]:
        dog = self.do(DogView(dog_id))
        return {'name': dog.name, 'tricks': tuple(dog.tricks)}
```

Write a test that covers your application's command and query methods.

```python
from eventsourcing.domain import put_metadata_in_context


def test_dog_school_with_dcb(app: DogSchoolWithEnduringObjects | DogSchoolWithSlices) -> None:
    # Get current max sequence position.
    head = app.events.recorder.head()

    # Evolve application state.
    context = {
        "user_id": "user-123",
    }
    with put_metadata_in_context(context):
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

    # Check the events.
    assert events[0].tags == [dog_id]
    assert events[1].tags == [dog_id]
    assert events[2].tags == [dog_id]
    assert isinstance(events[0].decision, DogRegistered)
    assert isinstance(events[1].decision, TrickAdded)
    assert isinstance(events[2].decision, TrickAdded)
    assert events[0].decision.dog_id, dog_id
    assert events[0].decision.name, 'Fido'
    assert events[1].decision.trick, 'roll over'
    assert events[2].decision.trick, 'play deead'
    assert events[0].metadata == context
    assert events[1].metadata == context
    assert events[2].metadata == context

```

Run the tests in memory.

```python
test_dog_school_with_dcb(DogSchoolWithEnduringObjects())

test_dog_school_with_dcb(DogSchoolWithSlices())
```

Run the tests with Postgres.

```python
postgres_env: dict[str, str] = {
    "PERSISTENCE_MODULE": 'eventsourcing.dcb.postgres_tt',
    "POSTGRES_DBNAME": "eventsourcing",
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "5432",
    "POSTGRES_USER": "eventsourcing",
    "POSTGRES_PASSWORD": "eventsourcing",
}

test_dog_school_with_dcb(
    DogSchoolWithEnduringObjects(env=postgres_env)
)

test_dog_school_with_dcb(
    DogSchoolWithSlices(env=postgres_env)
)
```

Run the tests with UmaDB.

```python
umadb_env: dict[str, str] = {
    "PERSISTENCE_MODULE": 'eventsourcing_umadb',
    "UMADB_URI": 'http://localhost:50051',
}

test_dog_school_with_dcb(
    DogSchoolWithEnduringObjects(env=umadb_env)
)

test_dog_school_with_dcb(
    DogSchoolWithSlices(env=umadb_env)
)
```


See the [documentation](https://eventsourcing.readthedocs.io/) for more information.


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
[Axon Server](https://github.com/pyeventsourcing/eventsourcing-axonserver#readme) and
[KurrentDB](https://github.com/pyeventsourcing/eventsourcing-kurrentdb#readme).
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

