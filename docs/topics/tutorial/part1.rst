===================================
Tutorial - Part 1 - Getting started
===================================

This tutorial provides a very gradual introduction to event-sourced aggregates and
applications, explaining just enough of the design and the mechanics of this library
to help users understand how things work. It expands and explains the
:ref:`Synopsis <Synopsis>`, and prepares new users of the library for reading
the :doc:`Modules </topics/modules>` documentation.


Overview
========

Software is often created to support some useful or important activities.
This kind of software is commonly separated into four layers. Users generally
interact with an interface layer, using some kind of user interface technology.
The interface layer depends on an application layer, which provides support for users of the software
independently of any particular interface technology. The application layer depends
on two other layers: the domain layer and the persistence layer. The domain layer
contains the "logic" of the application, and the persistence layer is responsible
for storing the current state of the application by using some kind of database
technology.

The interface layer might be a graphical user interface that directly connects to the
application layer, or a remote client that connects to a server such as Web browser and
Web server where the interface is partly in the client and partly on the server, or a
mobile application that works in a similar way. The interface layer might also be a suite
of test cases, that directly uses the application layer. When developing a new piece of
software, it can make good sense to start by writing tests that represent what a user
might usefully do with the software. An application can then be developed to pass these
tests. A Web or graphical user interface or mobile app can then be developed that uses
the application, repeating the commands and queries that were expressed in the tests. In
practice, these things would be developed together, by writing a small test, changing
the application code to pass the test, adjusting the user interface so that it makes use
of the new functionality, and then repeating this cycle until the software adequately
supports the useful or important activities it was intended to support.

The application layer is the thing your interface layer interacts with. The application
layer handles "commands" and "queries" that will be issued through the interface by the users
of your software. The application handles these commands and queries by interacting with the
domain and persistence layers. The application layer combines the domain layer with the
persistence layer, which do not otherwise interact with each other. The application layer
interacts with the domain layer so that the state of the application can evolve in a logical
and coherent way. The application layer interacts with the persistence layer so that the state
of the application can be stored and retrieved, so that the state of the application will endure
after the software stops running, and so that the state of the application can be obtained when
the software is used again in future. The state is changed in response to commands from the
interface, which are responded to in the application by it making decisions as a function of
its current state. The commands from the user are usually made by the user with some understanding
of the current state of the application, and of what they are trying to accomplish by using
the software. So that users can issue meaningful commands, the state of the application must
somehow be presented to the user. The state of an application is commonly presented to users
in a set of "views". The state of the application is presented by the application through the
interface to users by responding to queries that inform these views. For this reason, a test
case will generally give a command to the application in the expectation that that application
state will be changed in some particular kind of way, and then the test will check the expectation
is satisfied by checking the result of a query. When developing software, consideration must
therefore be given both to the commands and they way in which they will be handled (what decisions
the application will make) and also the way in which the state of the application will need to be
viewed and navigated by user (what decisions the user will make).

The domain layer involves a "model" which in *Domain-Driven Design* comprises a collection
of "aggregates", perhaps several different types. Although *Domain-Driven Design* is an
approach for the analysis and design of complex software systems, the partitioning of
application state across a set of aggregates is more generally applicable. Aggregates
each have a current "state". Together, the state of the aggregates determines the state
of the application. The aggregates have "behaviour" by which the state is evolved.
This behaviour is simply a collection of functions that make decisions. The decisions are
a function of the current state of the aggregate and the "commands" issued by users through
the interface and application. The state of an aggregate is evolved through a sequence
of decisions. And the state of the application is evolved through many individual sequences
of decisions. These decisions affect the current state, changing both the conditions within
which future decisions will be made, and the result of future queries. Because the views
may involve many aggregates, there is a tension between a design that will best support
the commands and a design that will best support the queries. This is the reason for
sometimes wanting to separate a "command model" in which the aggregate decisions are
recorded from a "query model" into which the state of the application is projected.
This is the realm of "event processing", of "event-driven systems", of "CQRS", and of
"materialized views". However, in many cases there is no immediate need to develop
separate command and query models. The aggregates themselves are often sufficient
to inform the views, and the user can then issue commands that will be handled by
the aggregates.

Finally, the persistence layer involves the way in which the current state is stored, so
that it is available in future and not lost when the software stops running. It makes good
sense to separate this concern from the concerns described above, so that tests can be
developed with a persistence layer that is fast and easy to use, and then the software
can be deployed for users with a database that is operationally capable of supporting
their needs.

Below we will review Python classes, then discuss event-sourced aggregates, and then
turn our attention to event-sourced applications.


Python classes
==============

This tutorial depends on a basic understanding of
`Python classes <https://docs.python.org/3/tutorial/classes.html>`_.

For example, we can define a ``Dog`` class in Python as follows.

.. code-block:: python

    class Dog:
        def __init__(self, name):
            self.name = name
            self.tricks = []

        def add_trick(self, trick):
            self.tricks.append(trick)

This example is taken from the `Class and Instance Variables
<https://docs.python.org/3/tutorial/classes.html#class-and-instance-variables>`_
section of the Python docs.

Having defined a Python class, we can use it to create an instance.

.. code-block:: python

    dog = Dog('Fido')


The ``dog`` object is an instance of the ``Dog`` class.

.. code-block:: python

    assert isinstance(dog, Dog)


The ``__init__()`` method initialises the attributes ``name`` and ``tricks``.

.. code-block:: python

    assert dog.name == 'Fido'
    assert dog.tricks == []

The method ``add_trick()`` appends the argument ``trick`` to the attribute ``tricks``.

.. code-block:: python

    dog.add_trick('roll over')
    assert dog.tricks == ['roll over']

This is a simple example of a Python class.

In the next section, we convert the ``Dog`` class to be an event-sourced aggregate.

Event-sourced aggregate
=======================

A persistent object that changes through a sequence of decisions
corresponds to the notion of an 'aggregate' in the book *Domain-Driven Design*.
In the book, aggregates are persisted by inserting or updating
database records that represent the current state of the object.

An event-sourced aggregate is persisted by recording the sequence of decisions
that it makes as a sequence of 'events'. This sequence of events is used to reconstruct
the current state of the aggregate. In earlier approaches to application architecture,
only the current state was persisted. The stored state was then updated as further
decisions were made. However, recording changing state brings several complications,
which are avoided by recording the decisions made by a domain model. Recording
the decisions, which do not change, is a more solid foundation on which to build
applications. Recording domain model decisions, and using them as the "source of
truth" in an application, is commonly termed "event sourcing".

We can convert the ``Dog`` class into an event-sourced aggregate using
the ``Aggregate`` class and ``@event`` decorator from the library's
:doc:`domain module </topics/domain>`. Events will be triggered when
decorated methods are called. The changes are highlighted below.

.. code-block:: python
    :emphasize-lines: 3,4,9

    from eventsourcing.domain import Aggregate, event

    class Dog(Aggregate):
        @event('Registered')
        def __init__(self, name):
            self.name = name
            self.tricks = []

        @event('TrickAdded')
        def add_trick(self, trick):
            self.tricks.append(trick)


As before, we can call the class to create a new instance.

.. code-block:: python

    dog = Dog('Fido')

The object is an instance of ``Dog``. It is also an ``Aggregate``.

.. code-block:: python

    assert isinstance(dog, Dog)
    assert isinstance(dog, Aggregate)

As we might expect, the attributes ``name`` and ``tricks`` have been initialised.

.. code-block:: python

    assert dog.name == 'Fido'
    assert dog.tricks == []


The ``dog`` aggregate also has an ``id`` attribute. The ID is used to uniquely identify
the aggregate within a collection of aggregates. It happens to be a UUID.

.. code-block:: python

    from uuid import UUID

    assert isinstance(dog.id, UUID)


As above, we can call the method ``add_trick()``. The given value is appended to ``tricks``.

.. code-block:: python

    dog.add_trick('roll over')

    assert dog.tricks == ['roll over']

By redefining the ``Dog`` class as an event-sourced aggregate in this way, we can generate a sequence
of event objects that can be recorded and used later to reconstruct the aggregate.

We can get the events from the aggregate by calling ``collect_events()``.

.. code-block:: python

    events = dog.collect_events()


We can then reconstruct the aggregate by calling ``mutate()`` on the collected event objects.

.. code-block:: python

    copy = None
    for e in events:
        copy = e.mutate(copy)

    assert copy == dog


Event-sourced aggregates can be developed and tested independently.

.. code-block:: python

    def test_dog():
        dog = Dog('Fido')
        assert dog.name == 'Fido'
        assert dog.tricks == []

        dog.add_trick('roll over')
        assert dog.tricks == ['roll over']

    # Run the test
    test_dog()


However, event-sourced aggregates are normally used within an application object, so
that aggregate events can be stored in a database, and so that aggregates can
be reconstructed from stored events.


Event-sourced application
=========================

This library has "application objects" which simply implements this layered architecture
for a particular scope of concern. So that an application object supports a particular
set of commands and queries, has a particular set of aggregates, and uses a particular
database.

Event-sourced applications combine event-sourced aggregates
with a persistence mechanism to store and retrieve aggregate events.

We can define event-sourced applications with the ``Application`` class
from the library's :doc:`application module </topics/application>`.

.. code-block:: python

    from eventsourcing.application import Application


We can save aggregates with the application's ``save()`` method, and
reconstruct previously saved aggregates with the application repository's
``get()`` method.

Let's define a ``DogSchool`` application that uses the ``Dog`` aggregate class.

.. code-block:: python

    class DogSchool(Application):
        def register_dog(self, name):
            dog = Dog(name)
            self.save(dog)
            return dog.id

        def add_trick(self, dog_id, trick):
            dog = self.repository.get(dog_id)
            dog.add_trick(trick)
            self.save(dog)

        def get_dog(self, dog_id):
            dog = self.repository.get(dog_id)
            return {'name': dog.name, 'tricks': tuple(dog.tricks)}

The "command" methods ``register_dog()`` and ``add_trick()`` evolve application
state, and the "query" method ``get_dog()`` presents current state.

We can construct an instance of the application by calling the application class.

.. code-block:: python

    application = DogSchool()


We can then create and update aggregates by calling the command methods of the application.

.. code-block:: python

    dog_id = application.register_dog('Fido')
    application.add_trick(dog_id, 'roll over')
    application.add_trick(dog_id, 'fetch ball')


We can view the state of the aggregates by calling application query methods.

.. code-block:: python

    dog_details = application.get_dog(dog_id)

    assert dog_details['name'] == 'Fido'
    assert dog_details['tricks'] == ('roll over', 'fetch ball')

And we can propagate the state of the application as a whole by selecting
event notifications from the application's notification log.

.. code-block:: python

    notifications = application.notification_log.select(start=1, limit=10)

    assert len(notifications) == 3
    assert notifications[0].id == 1
    assert notifications[1].id == 2
    assert notifications[2].id == 3

Many different kinds of event-sourced applications can
be defined in this way.


Project structure
=================

You are free to structure your project files however you wish. You
may wish to put your application class in a file named ``application.py``,
your aggregate classes in a file named ``domainmodel.py``, and your
tests in a separate folder.

::

    your_project/__init__.py
    your_project/application.py
    your_project/domainmodel.py
    tests/__init__.py
    tests/test_application.py

It is generally recommended to put test code and code under test in separate
folders.

Writing tests
=============

It is generally recommended to follow a test-driven approach to the development of
event-sourced applications. You can get started with your event sourcing project by
first writing a failing test in a Python file, for example a file ``test_application.py``.
You can begin by defining your application and aggregate classes in this file. You
can then refactor by moving aggregate and application classes to separate Python
modules. You can convert these modules to packages if you want to split things up
into smaller modules.

.. code-block:: python

    def test_dog_school():

        # Construct application object.
        app = DogSchool()

        # Call application command methods.
        dog_id = app.register_dog('Fido')
        app.add_trick(dog_id, 'roll over')
        app.add_trick(dog_id, 'fetch ball')

        # Call application query method.
        assert app.get_dog(dog_id) == {
            'name': 'Fido',
            'tricks': ('roll over', 'fetch ball'),
        }

Video
=====

.. raw:: html

    <div style="position:relative;padding-bottom:63.5%;">
      <iframe style="width:100%;height:100%;position:absolute;left:0px;top:0px;"
        src="https://www.youtube.com/embed/V1iKSn7Fark" title="YouTube video player"
        frameborder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen>
      </iframe>
    </div>

Exercise
========

Try it for yourself by copying the code snippets above into your IDE, and running the test.

.. code-block:: python

    test_dog_school()

Alternatively use the :ref:`project template <Template>`.

Next steps
==========

* For more information about event-sourced aggregates, please
  read :doc:`Part 2 </topics/tutorial/part2>` of this tutorial.
* For more information about event-sourced applications, please
  read :doc:`Part 3 </topics/tutorial/part3>` of this tutorial.
