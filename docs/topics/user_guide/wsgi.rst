================================================
Using with Web Frameworks and Task Queue Workers
================================================

In general, you need one and only one instance of your application
for each process. If your eventsourcing application object has policies
that subscribe to events, constructing more than one instance of the
application in a process will result in, for example, multiple attempts
to store an event, which won't work.

One arrangement (see below) is to have a module with a module-level
variable and two module-level functions ``init_application()`` and
``get_application()``. The function ``init_application()`` will
construct the application object and can be called from a suitable
hook or signal. Then calls to ``get_application()`` can be made from
functions that handle requests, if they require the application's
services.

The functions below have been written so that ``init_application()``
will raise an exception if it is called more than once, and also
``get_application()`` will raise an exeception unless ``init_application()``
has been called.

.. code:: python

    class Application(object):
        """My eventsourcing application."""

    application = None

    def construct_application(datastore):
        return Application(datastore)

    def init_application(datastore):
        global application
        if application is not None:
            raise AssertionError("init_application() has already been called")
        application = construct_application(datastore)

    def get_application():
        if application is None:
            raise AssertionError("init_application() must be called first")
        return application


In your test suite, you may need or wish to setup the application more
than once. In that case, you will also need a ``close_application()``
function that closes the application object, unsubscribing any handlers,
and resetting the module level variable so that ``init_application()`` can be
called again. If doesn't really matter if you don't close your application at
the end of the process lifetime, however you may wish to close database
connections.

.. code:: python

    def close_application():
        global application
        if application is not None:
            application.close()
        application = None


Typically your eventsourcing application object will be constructed after
a database connection has been setup, and before any requests are handled.
Requests handlers can then safely use the already constructed application
object without any risk of race conditions causing the application to be
constructed more than once.

Making connections to databases is out of scope of the eventsourcing
application classes, and should be setup in a normal way. The documentation
for your Web or worker framework may describe when to make a
database connection, and your database documentation may also have some
suggestions. It is recommended to make use of any hook or decorator or signals
intended for this purpose. See below for suggestions.


Web Tier
========

This section contains suggestions for using uWSGI in prefork mode with Django, and
with Flask.

uWSGI
-----

uWSGI has a ``@postfork`` `decorator
<http://uwsgi-docs.readthedocs.io/en/latest/PythonDecorators.html#uwsgidecorators.postfork>`__
that can be used with Django and Flask and other frameworks.


Flask
"""""

Flask application can use ``init_application()`` and ``get_application()``.

.. code:: python

    from flask import Flask
    from uwsgidecorators import postfork

    # Use uwsgi decorator to initialise the process.
    @postfork
    def init_process():
        # Setup database connection for this process.
        database = {}
        # Construct application for this process.
        init_application(database)

    from flask import Flask
    app = Flask(__name__)

    # Use Flask app to route request to view.
    @app.route('/')
    def hello_world():
        # Use eventsourcing application to construct response.
        app = get_application()
        return "Hello World, {}".format(app)


Django
""""""

Django WSGI file can use ``init_application()``.

.. code:: python

    from django.core.wsgi import get_wsgi_application
    from uwsgidecorators import postfork

    @postfork
    def init_process():
        # Setup database connection for this process.
        database = {}
        # Construct application for this process.
        init_application(database)

    application = get_wsgi_application()



Django views can use ``get_application()``.

.. code:: python

    from django.http import HttpResponse

    def hello_world(request):
        # Use eventsourcing application to construct response.
        app = get_application()
        html = "<html><body>Hello world, {}</body></html>".format(app)
        return HttpResponse(html)


Worker Tier
===========

This section contains suggestions for using the Celery distributed task queue.


Celery
------

Celery has a ``worker_process_init`` `signal
<http://docs.celeryproject.org/en/latest/userguide/signals.html#worker-process-init>`__.

.. code:: python

    from celery import Celery
    from celery.signals import worker_process_init

    app = Celery()

    @worker_process_init.connect
    def init_process(sender=None, conf=None, **kwargs):
        # Setup database connection for this process.
        database = {}
        # Construct application for this process.
        init_application(database)

    # Use Celery app to route the task to the worker.
    @app.task
    def hello_world():
        # Use eventsourcing app to complete the task.
        app = get_application()
        return "Hello World, {}".format(app)
