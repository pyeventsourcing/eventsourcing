====================================================
Using with Web Frameworks/WSGI/Message Queue Workers
====================================================

Typically, you will need one (and only one) instance of your application
object for each request handling process. That is because if your eventsourcing
application object has any policies that subscribe to events, it is necessary
to avoid constructing more than one eventsourcing application object per process.
Otherwise duplicate policies will exist, event handlers will be subscribed more
times than they should be, and commands that should be executed once per event
will be executed several times by mistake. For example, if your application has
a persistence policy and more than one object has been constructed in the same
process, then attempts to persist events will be duplicated, which won't work.

Connections to databases are out of scope of the eventsourcing application class,
and should be setup in a normal way. The documentation for your Web or worker
framework probably describes how and when to setup database connections, and
your database documentation may also have some suggestion.

In general, if your request handling process will have been forked (e.g. in
preforked Web or worker tier), then connections to databases can be setup after
child processes are forked. It is commonly recommended to make use of any
"postfork" hook or decorator or signal intended for this purpose.

Typically, your eventsourcing application object will be constructed
after a child process has been forked, after a database connection
has been setup, and before any requests are handled. Request handlers
can then use the already constructed object.

One arrangement is to have a module in your eventsourcing application
with a module-level variable ``application``, and two module-level functions
``init_application()`` and ``get_application()``. The function
``init_application()`` can be called from a suitable hook or signal and
you can call ``get_application()`` from any functions that handle requests.
You can arrange these functions to make sure the ``init_application()`` is
called only once, and to make sure that ``init_application()`` is called
before ``get_application()`` is called.

If you have a test suite, you may wish to setup and teardown the application
for each test. In that case, you will also need a ```close_application()```
function that closes the application object, unsubscribing any handlers,
and resets the module level variable.

If doesn't matter if you don't close your application at the end of the process
lifetime, but in order to conserve resources you may wish to pay attention to
closing database connections, and any other connections that have been opened
by the process. Again, closing database connections is out of the scope of the
eventsourcing application class.


.. code:: python

    class Application(object):
        """My eventsourcing application."""

    application = None

    def construct_application():
        return Application()

    def init_application():
        global application
        if application is not None:
            raise AssertionError("Application is already constructed")
        application = construct_application()

    def get_application():
        if application is None:
            raise AssertionError("init_application() must be called first")
        return application

    def close_application():
        global application
        if application is not None:
            application.close()
        application = None


uWSGI
=====

Uwsgi has a ``@postfork`` `decorator
<http://uwsgi-docs.readthedocs.io/en/latest/PythonDecorators.html#uwsgidecorators.postfork>`__
that can be used with Django and Flask and other frameworks.


Flask
=====

Example Flask application, using the uWSGI ``postfork`` decorator.

.. code:: python

    from flask import Flask
    from uwsgidecorators import postfork

    @postfork
    def init_process():
        # Setup database connection for this process.
        # ...

        # Construct application for this process.
        init_application()

    from flask import Flask
    app = Flask(__name__)

    @app.route('/')
    def hello_world():
        # Use eventsourcing application to construct response to request.
        app = get_application()
        return "Hello World"


Django
======

Example .wsgi file for a Django project, using the uWSGI ``postfork`` decorator.

.. code:: python

    from django.core.wsgi import get_wsgi_application
    from uwsgidecorators import postfork

    application = get_wsgi_application()

    @postfork
    def on_postfork():
        # Construct application for this process.
        init_application()


Example Django view.

.. code:: python

    from django.http import HttpResponse

    def hello_world(request):
        # Use eventsourcing application to construct response to request.
        app = get_application()
        html = "<html><body>Hello world</body></html>"
        return HttpResponse(html)


Celery
======

Celery has a ``worker_process_init`` `signal
<http://docs.celeryproject.org/en/latest/userguide/signals.html#worker-process-init>`__.

Example Celery worker.

.. code:: python

    from celery import Celery
    from celery.signals import worker_process_init

    app = Celery()

    @worker_process_init.connect
    def init_process(sender=None, conf=None, **kwargs):
        # Setup database connection for this process.
        # ...

        # Construct eventsourcing application for this process.
        init_application()

    @app.task
    def hello_world():
        # Use eventsourcing application to construct response to request.
        app = get_application()
        return "Hello World"
