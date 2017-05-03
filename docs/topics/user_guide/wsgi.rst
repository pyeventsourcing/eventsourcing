=====================================
Web frameworks and task queue workers
=====================================

In general, you will need one and only one instance of your application
in each process. If your eventsourcing application object has policies
that subscribe to events, constructing more than one instance of the
application will cause, for example, multiple attempts to store an event,
which won't work.

One arrangement is to have a module with a variable and two functions
(see below). The first function constructs the application object and
assigns it to the variable, and can be called from a suitable hook or
signal designed for setting things up before any requests are handled.
A second function returns the application object assigned to the variable,
and can be called by any request or task handlers that depend on the
application's services.

Although the first function must be called only once, the second function
may be called many times. The example functions below have been written
relatively strictly, so that ``init_example_application()`` will raise
an exception if it has already been called, and ``get_example_application()``
will raise an exeception if ``init_example_application()`` has not been called.

Please note, if your eventsourcing application depends on receiving a
database session object when it is constructed, for example if you are
using the SQLAlchemy library classes, you can add such an argument to
the signature of your ``init_example_application()`` and
``construct_example_application()`` functions.

.. code:: python

    # Your eventsourcing application.
    class ExampleApplication(object):
        pass


    def construct_example_application(**kwargs):
        return ExampleApplication(**kwargs)


    application = None


    def init_example_application(**kwargs):
        global application
        if application is not None:
            raise AssertionError("init_example_application() has already been called")
        application = construct_example_application(**kwargs)


    def get_example_application():
        if application is None:
            raise AssertionError("init_example_application() must be called first")
        return application


As an aside, if you will use these function also in your test suite, and your
test suite needs to setup the application more than once, you will also need
a ``close_example_application()`` function that closes the application object,
unsubscribing any handlers, and resetting the module level variable so that
``init_example_application()`` can be called again. If doesn't really matter
if you don't close your application at the end of the process lifetime, however
you may wish to close any database or other connections to network services.

.. code:: python

    def close_example_application():
        global application
        if application is not None:
            application.close()
        application = None


Typically, your eventsourcing application object will be constructed after
its database connection has been setup, and before any requests are handled.
Request handlers ("views" or "tasks") can then safely use the already
constructed application object without risk of a race condition causing
the application to be constructed more than once.

Setting up connections to databases is out of scope of the eventsourcing
application classes, and should be setup in a normal way. The documentation
for your Web or worker framework may describe when to setup database connections,
and your database documentation may also have some suggestions. It is recommended
to make use of any hooks or decorators or signals intended for the purpose of setting
up the database connection also to construct the application once for the process.
See below for some suggestions.



Web frameworks
==============

This section contains suggestions for Web framework users.

*Please note, the fragments of code in this section are merely suggestive, and unlike the
code snippets in the other sections of the user guide, do not form a working program. For
a working example using Flask and uWSGI, please refer to the library modules
:mod:`eventsourcing.example.flaskapp` and
:mod:`eventsourcing.example.flaskwsgi`.

uWSGI
-----

uWSGI has a `postfork decorator
<http://uwsgi-docs.readthedocs.io/en/latest/PythonDecorators.html#uwsgidecorators.postfork>`__
that can be used with Django and Flask and other frameworks. The ``@postfork``
may be appropriate if you are running uWSGI in prefork mode. Other decorators are
available.

Your ``wsgi.py`` file can have a module-level function decorated with the ``@postfork``
decorator that initialises your eventsourcing application for the Web application process
after child workers have been forked.

.. code:: python

    from uwsgidecorators import postfork

    @postfork
    def init_process():
        # Setup database connection.
        database = {}
        # Construct eventsourcing application.
        init_example_application()


Flask
-----

Flask views can use ``get_example_application()`` to construct their response.

.. code:: python

    from flask import Flask

    app = Flask(__name__)

    # Use Flask app to route request to view.
    @app.route('/')
    def hello_world():
        # Use eventsourcing application to construct response.
        app = get_example_application()
        return "Hello World, {}".format(id(app))


Django
------

Similarly, Django views can use ``get_example_application()`` to construct the response.

.. code:: python

    from django.http import HttpResponse

    def hello_world(request):
        # Use eventsourcing application to construct response.
        app = get_example_application()
        html = "<html><body>Hello World, {}</body></html>".format(id(app))
        return HttpResponse(html)


In both cases, database tables must be created before running the application.


Applause djangoevents project
-----------------------------

The excellent project `djangoevents <https://github.com/ApplauseOSS/djangoevents>`__
by `Applause <https://www.applause.com/>`__ is a Django app that provides a neat
way of taking an event sourcing approach in a Django project. It allows this library
to be used seamlessly with Django, by using the Django ORM to store events. Using
djangoevents is well documented in the README file. It adds some nice enhancements
to the capabilities of this library, and shows how various components can be
extended or replaced. Please note, the djangoevents project currently works with
a previous version of this library.


Task queue workers
==================

This section contains suggestions for Celery users.


Celery
------

Celery has a `worker_process_init signal decorator
<http://docs.celeryproject.org/en/latest/userguide/signals.html#worker-process-init>`__,
which may be appropriate if you are running Celery workers in prefork mode. Other decorators
are available.

Your Celery tasks or config module can have a module-level function decorated with
the ``@worker-process-init`` decorator that initialises your eventsourcing application
for the Celery worker process.


.. code:: python

    from celery.signals import worker_process_init

    @worker_process_init.connect
    def init_process(sender=None, conf=None, **kwargs):
        # Setup database connection.
        database = {}
        # Construct eventsourcing application.
        init_example_application()


Celery tasks can then use ``get_example_application()`` to complete the task.

.. code:: python

    from celery import Celery

    app = Celery()

    # Use Celery app to route the task to the worker.
    @app.task
    def hello_world():
        # Use eventsourcing app to complete the task.
        app = get_example_application()
        return "Hello World, {}".format(id(app))
