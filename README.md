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
# Import library classes.
from eventsourcing.application.simple import SimpleApplication
from eventsourcing.domain.model.aggregate import AggregateRoot

# Construct application, use as context manager.
with SimpleApplication(uri='sqlite:///:memory:') as app:

    # Create new event sourced object.
    obj = AggregateRoot.create()
    
    # Update object attribute.
    obj.change_attribute(name='a', value=1)
    assert obj.a == 1
    
    # Save all pending events atomically.
    obj.save()

    # Get object state from stored events.
    copy = app.repository[obj.id]
    assert copy.__class__ == AggregateRoot
    assert copy.a == 1

    # Discard the aggregate.
    copy.discard()
    copy.save()
    assert copy.id not in app.repository

    # Optimistic concurrency control.
    from eventsourcing.exceptions import ConcurrencyError
    try:
        obj.change_attribute(name='a', value=2)
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
