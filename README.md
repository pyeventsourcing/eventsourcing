# Event Sourcing in Python

[![Build Status](https://secure.travis-ci.org/johnbywater/eventsourcing.png)](https://travis-ci.org/johnbywater/eventsourcing)
[![Coverage Status](https://coveralls.io/repos/github/johnbywater/eventsourcing/badge.svg)](https://coveralls.io/github/johnbywater/eventsourcing)

A library for event sourcing in Python.

## Installation

Use pip to install the [stable distribution](https://pypi.python.org/pypi/eventsourcing) from
the Python Package Index.

    $ pip install eventsourcing


## Documentation

Please refer to [the documentation](http://eventsourcing.readthedocs.io/) for installation and usage guides.


## Synopsis

```python
from eventsourcing.application.simple import SimpleApplication
from eventsourcing.domain.model.aggregate import AggregateRoot


class World(AggregateRoot):
    def __init__(self, *args, **kwargs):
        super(World, self).__init__(*args, **kwargs)
        self.history = []

    def make_it_so(self, something):
        self._trigger(World.SomethingHappened, what=something)

    class SomethingHappened(AggregateRoot.Event):
        def mutate(self, obj):
            obj = super(World.SomethingHappened, self).mutate(obj)
            obj.history.append(self)
            return obj
            
            
# Construct application.
with SimpleApplication(uri='sqlite:///:memory:') as app:

    # Create new aggregate.
    world = World.create()
    
    # Execute commands.
    world.make_it_so('dinosaurs')
    world.make_it_so('trucks')
    world.make_it_so('internet')

    # Check current state.
    assert world.history[0].what == 'dinosaurs'
    assert world.history[1].what == 'trucks'
    assert world.history[2].what == 'internet'

    # Save pending events.
    world.save()

    # Replay stored events.
    obj = app.repository[world.id]
    assert obj.__class__ == World
    
    # Check retrieved state.
    assert obj.id == world.id
    assert obj.history[0].what == 'dinosaurs'
    assert obj.history[1].what == 'trucks'
    assert obj.history[2].what == 'internet'

    # Discard aggregate.
    world.discard()
    world.save()

    # Aggregate not in repository. 
    assert world.id not in app.repository

    # Optimistic concurrency control.
    from eventsourcing.exceptions import ConcurrencyError
    obj.make_it_so('future')
    try:
        obj.save()
    except ConcurrencyError:
        pass
    else:
        raise Exception("Shouldn't get here")
```

## Project

This project is [hosted on GitHub](https://github.com/johnbywater/eventsourcing).
Please [register your questions, requests and any other issues](https://github.com/johnbywater/eventsourcing/issues).

## Slack Channel

There is a [Slack channel](https://eventsourcinginpython.slack.com/messages/@slackbot/) for this project, which you are [welcome to join](https://join.slack.com/t/eventsourcinginpython/shared_invite/enQtMjczNTc2MzcxNDI0LTUwZGQ4MDk0ZDJmZmU0MjM4MjdmOTBlZGI0ZTY4NWIxMGFkZTcwNmUxM2U4NGM3YjY5MTVmZTBiYzljZjI3ZTE).
