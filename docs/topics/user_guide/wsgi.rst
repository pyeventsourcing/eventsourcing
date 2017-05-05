=====================================
Web frameworks and task queue workers
=====================================

There are many frameworks, many databases, and various process or
execution models. This section gives an overview of the concerns,
and indicates how they can be resolved in different situations.

Please note, unlike the code snippets in the other sections of
the user guide, the snippets of code in this section are merely
suggestive, and do not form a complete working program.
For a working example using eventsourcing and Flask and
SQLAlchemy, please refer to the library module
:mod:`eventsourcing.example.interface.flaskapp`, which is
tested both stand-alone and with uWSGI.


Application object
==================

In general you need one, and only one, instance of your application
object in each process.
If your eventsourcing application object has any policies, then
constructing more than one instance of the application causes the
policy event handlers to be subscribed more than once, so for example
more than one attempt will be made to save each event, which won't
work.

To make sure there in only one instance of your application object in
each process, one possible arrangement (see below) is to have a module
with a variable and two functions. The first function constructs the
application object and assigns it to the variable, and can be called
from a suitable hook or signal designed for setting things up before
any requests are handled. A second function returns the application
object assigned to the variable, and can be called by any request or
task handlers that depend on the application's services. An alternative
to having separate "init" and "get" functions is having one function
that does lazy initialization of the application object when first
requested.

Although the first function below must be called only once, the second
function may be called many times. The example functions below have
been written relatively strictly, so that ``init_application()`` will
raise an exception if it has already been called, and ``get_application()``
will raise an exeception if ``init_application()`` has not been called.

.. code:: python

    # Your eventsourcing application.
    class ExampleApplication(object):
        pass


    def construct_application(**kwargs):
        return ExampleApplication(**kwargs)


    application = None


    def init_application(**kwargs):
        global application
        if application is not None:
            raise AssertionError("init_application() has already been called")
        application = construct_application(**kwargs)


    def get_application():
        if application is None:
            raise AssertionError("init_application() must be called first")
        return application


As an aside, if you will use these function also in your test suite, and your
test suite needs to setup the application more than once, you will also need
a ``close_application()`` function that closes the application object,
unsubscribing any handlers, and resetting the module level variable so that
``init_application()`` can be called again. If doesn't really matter
if you don't close your application at the end of the process lifetime, however
you may wish to close any database or other connections to network services.

.. code:: python

    def close_application():
        global application
        if application is not None:
            application.close()
        application = None



Database connection
===================

If your eventsourcing application depends on receiving a database session
object when it is constructed, for example if you are using the SQLAlchemy
classes in this library, then you will need to create a session object first
and use it to construct the application object.

On the other hand, if your eventsourcing application does not depend on
receiving a database session object when it is constructed, for example if
you are using the Cassandra classes in this library, then you may construct
the application object before configuring the database connection - just be
careful not to use the application object before the database connection is
established.

Typically, your eventsourcing application object will be constructed after
its database connection has been setup, and before any requests are handled.
Request handlers ("views" or "tasks") can then safely use the already
constructed application object without risk of a race condition leading to
the application being constructed more than once.

Setting up connections to databases is out of scope of the eventsourcing
application classes, and should be setup in a "normal" way. The documentation
for your Web or worker framework may describe when to setup database connections,
and your database documentation may also have some suggestions. It is recommended
to make use of any hooks or decorators or signals intended for the purpose of setting
up the database connection also to construct the application once for the process.
See below for some suggestions.


SQLAlchemy
----------

SQLAlchemy has `very good documentation about constructing sessions
<http://docs.sqlalchemy.org/en/latest/orm/session_basics.html>`__.

.. pull-quote::

    *Some web frameworks include infrastructure to assist in the task of aligning
    the lifespan of a Session with that of a web request. This includes products
    such as* `Flask-SQLAlchemy <http://flask-sqlalchemy.pocoo.org/>`__, *for usage
    in conjunction with the Flask web framework, and* `Zope-SQLAlchemy
    <https://pypi.python.org/pypi/zope.sqlalchemy>`__, *typically used with the
    Pyramid framework. SQLAlchemy recommends that these products be used as
    available.*

    *In those situations where the integration libraries are not provided or are
    insufficient, SQLAlchemy includes its own “helper” class known as scoped_session.
    A tutorial on the usage of this object is at Contextual/Thread-local Sessions. It
    provides both a quick way to associate a Session with the current thread, as well
    as patterns to associate Session objects with other kinds of scopes.*

The important thing is to use a scoped session, and it is better
to have the session scoped to the request or task, rather than
the thread, but scoping to the thread is ok.

If you are an SQLAlchemy user, it is well worth reading the
documentation about sessions.


Cassandra
---------

Cassandra connections can be setup entirely independently of the application
object. See the section about :doc:`using Cassandra</topics/user_guide/cassandra>`
for more information.


Web frameworks
==============

uWSGI
-----

If you are running uWSGI in prefork mode, and not using a framework to
to initialise the database or provide a signal to initialise the
application object, uWSGI has a `postfork decorator
<http://uwsgi-docs.readthedocs.io/en/latest/PythonDecorators.html#uwsgidecorators.postfork>`__
that may be used for this purpose.

Your ``wsgi.py`` file can have a module-level function decorated with the ``@postfork``
decorator that initialises your eventsourcing application for the Web application process
after child workers have been forked.

.. code:: python

    from uwsgidecorators import postfork

    @postfork
    def init_process():
        # Set up database connection.
        database = {}
        # Construct eventsourcing application.
        init_application()

Other decorators are available.


Flask-SQLAlchemy
----------------

If you wish to use eventsourcing with Flask and SQLAlchemy, then you may wish
to use Flask-SQLAlchemy. You just need to define your active record class
using the model classes from that library, and then use it instead of the
library classes in your eventsourcing application object, along with the
session object it provides.

For a working example using Flask and SQLAlchemy, please
refer to the library module :mod:`eventsourcing.example.interface.flaskapp`,
which is tested both stand-alone and with uWSGI. That example uses
Flask-SQLAlchemy to setup session object that is scoped to the request.
The application is initialised using Flask's 'before_first_request'
signal.

.. code:: python

    application = Flask(__name__)

    db = SQLAlchemy(application)


    @application.before_first_request
    def init_example_application_with_sqlalchemy():
        active_record_strategy = SQLAlchemyActiveRecordStrategy(
            active_record_class=IntegerSequencedItemRecord,
            session=db.session,
        )
        init_example_application(
            entity_active_record_strategy=active_record_strategy
        )


Flask with Cassandra
--------------------

The `Cassandra Driver FAQ <https://datastax.github.io/python-driver/faq.html>__`
has a code snippet about establishing the connection with the uWSGI `postfork`
decorator, when running in a forked mode.

.. code:: python

    from flask import Flask
    from uwsgidecorators import postfork
    from cassandra.cluster import Cluster

    session = None
    prepared = None

    @postfork
    def connect():
        global session, prepared
        session = Cluster().connect()
        prepared = session.prepare("SELECT release_version FROM system.local WHERE key=?")

    app = Flask(__name__)

    @app.route('/')
    def server_version():
        row = session.execute(prepared, ('local',))[0]
        return row.release_version


Flask-Cassandra
---------------

The `Flask-Cassandra <https://github.com/TerbiumLabs/flask-cassandra>`__
project serves a similar function to Flask-SQLAlchemy.


Django-Cassandra
----------------

If you wish to use eventsourcing with Django and Cassandra, you may wish
to use `Django-Cassandra <https://pypi.python.org/pypi/django-cassandra-engine/>`__.

It's also possible to use this library directly with Django and Cassandra. You
just need to configure the connection and initialise the application before handling
requests in a way that is correct for your configuration.


Django ORM
----------

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
        # Set up database connection.
        database = {}
        # Construct eventsourcing application.
        init_application()


As an alternative, it may work to use decorator ``@task_prerun``
with a getter that supports lazy initialization.

.. code:: python

    from celery.signals import task_prerun
    @task_prerun.connect
    def init_process(*args, **kwargs):
        get_appliation(lazy_init=True)


If you use lazy initialization, it might be safer to lock the section
that constructs the application object, and check inside the locked
block that the application object still doesn't exist before constructing
it (you don't want to keep locking the application object just to get it).

Once the application has been safely initialized once
in the process, your Celery tasks can use function ``get_application()``
to complete their work.

.. code:: python

    from celery import Celery

    app = Celery()

    # Use Celery app to route the task to the worker.
    @app.task
    def hello_world():
        # Use eventsourcing app to complete the task.
        app = get_application()
        return "Hello World, {}".format(id(app))
