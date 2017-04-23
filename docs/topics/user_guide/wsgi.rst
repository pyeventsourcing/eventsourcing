================================================
Using with Web Frameworks and Task Queue Workers
================================================

In general, you will need one and only one instance of your application
in each process. If your eventsourcing application object has policies
that subscribe to events, constructing more than one instance of the
application will cause, for example, multiple attempts to store an event,
which won't work.

One arrangement is to have a module with a variable and two
functions perhaps called ``init_example_application()`` and
``get_example_application()`` (see below). The function
``init_example_application()`` will construct the application
object and can be called from a suitable hook or signal. Then
calls to ``get_example_application()`` can be made from functions
that handle requests, if they require the application's services.

The functions below have been written so that ``init_example_application()``
will raise an exception if it is called more than once, and also
``get_example_application()`` will raise an exeception unless
``init_example_application()`` has been called.

Please note, if your eventsourcing application depends on receiving a
database session object when it is constructed, for example if you are
using the SQLAlchemy library classes, you can add such an argument to
the signature of your ``init_example_application()`` and ``construct_example_application()``
functions.

.. code:: python

    # Your eventsourcing application.

    class ExampleApplication(object):
        """
        My eventsourcing application.
        """


    def construct_example_application():
        return ExampleApplication()


    application = None


    def init_example_application():
        global application
        if application is not None:
            raise AssertionError("init_example_application() has already been called")
        application = construct_example_application()


    def get_example_application():
        if application is None:
            raise AssertionError("init_example_application() must be called first")
        return application


In your test suite, you may need or wish to setup the application more
than once. In that case, you will also need a ``close_example_application()``
function that closes the application object, unsubscribing any handlers,
and resetting the module level variable so that ``init_example_application()`` can be
called again. If doesn't really matter if you don't close your application at
the end of the process lifetime, however you may wish to close database
connections.

.. code:: python

    def close_example_application():
        global application
        if application is not None:
            application.close()
        application = None


Typically your eventsourcing application object will be constructed after
a database connection has been setup, and before any requests are handled.
Requests handlers ("views" or "tasks") can then safely use the already
constructed application object without any risk of race conditions causing
the application to be constructed more than once.

Setting up connections to databases is out of scope of the eventsourcing
application classes, and should be setup in a normal way. The documentation
for your Web or worker framework may describe when to setup database connections,
and your database documentation may also have some suggestions. It is recommended
to make use of any hooks or decorators or signals intended for this purpose. See
below for some suggestions.


Web Tier
========

This section contains suggestions for uWSGI users. The fragments of code in this section
are merely suggestive. For a working example Flask application and WSGI file, please
refer to the modules ``flaskapp`` and ``flaskwsgi`` in ``eventsourcing.example.app``.

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


Django views can then use ``get_example_application()`` to construct the response.

.. code:: python

    from django.http import HttpResponse

    def hello_world(request):
        # Use eventsourcing application to construct response.
        app = get_example_application()
        html = "<html><body>Hello World, {}</body></html>".format(id(app))
        return HttpResponse(html)


Similarly, Flask views can use ``get_example_application()`` to construct the response.

.. code:: python

    from flask import Flask

    app = Flask(__name__)

    # Use Flask app to route request to view.
    @app.route('/')
    def hello_world():
        # Use eventsourcing application to construct response.
        app = get_example_application()
        return "Hello World, {}".format(id(app))


In both cases, you will need to setup tables before running the application.

Worker Tier
===========

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
