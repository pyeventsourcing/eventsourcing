================================================
Using with Web Frameworks and Task Queue Workers
================================================

In general, you need one and only one instance of your application
for each process. If your eventsourcing application object has policies
that subscribe to events, constructing more than one instance of the
application in a process will result in for example multiple attempt
to store an event, which won't work.

One arrangement is to have a module somewhere in your application packages
with a module-level variable ``application``, and two module-level functions
``init_application()`` and ``get_application()``. The function
``init_application()`` will construct the application object and can be
called from a suitable hook or signal and. Then calls to ``get_application()``
can be made from any functions that handle requests that require the application's
services. These functions can be arranged strictly to make sure the ``init_application()``
is called only once, and to ensure ``init_application()`` was called
before ``get_application()``.

.. code:: python

    class Application(object):
        """My eventsourcing application."""

    application = None

    def construct_application(datastore):
        return Application(datastore)

    def init_application(datastore):
        global application
        if application is not None:
            raise AssertionError("Application is already constructed")
        application = construct_application(datastore)

    def get_application():
        if application is None:
            raise AssertionError("init_application() must be called first")
        return application

..    def close_application():
        global application
        if application is not None:
            application.close()
        application = None


If your process model involves forking child workers, typically your
eventsourcing application object will be constructed during the
intitialisation of the child process, after a database connection
has been setup, and before any requests are handled. Request handlers
can then use the already constructed object without risk of race
conditions leading to duplicate event handler subscriptions.

Making connections to databases is out of scope of the eventsourcing
application classes, and should be setup in a normal way. The documentation
for your Web or worker framework may describe when to make a
database connection, and your database documentation may also have some
suggestions.

It is commonly recommended to make use of any "postfork" hook or
decorator or signal intended for this purpose.

.. If you have a test suite, you may wish to setup and teardown the application
for each test. In that case, you will also need a ```close_application()```
function that closes the application object, unsubscribing any handlers,
and resets the module level variable.

If doesn't matter if you don't close your application at the end of the
process lifetime, but to conserve resources you may wish to pay attention
to closing database connections, and any other connections that have been opened
by the process. Again, closing database connections is out of the scope of the
eventsourcing application class.


Web Tier
========


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
