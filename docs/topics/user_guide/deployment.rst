==========
Deployment
==========

This section gives an overview of the concerns that arise
when using an eventsourcing application in Web applications
and task queue workers. There are many combinations of
frameworks, databases, and process models. The complicated
aspect is setting up the database configuration to work well
with the framework. Your event sourcing application can be
constructed just after the database is configured, and before
requests are handled.

Please note, unlike the code snippets in the other sections of
the user guide, the snippets of code in this section are merely
suggestive, and do not form a complete working program.
For a working example using Flask and SQLAlchemy, please refer
to the library module :mod:`eventsourcing.example.interface.flaskapp`,
which is tested both stand-alone and with uWSGI.


Application object
==================

In general you need one, and only one, instance of your application
object in each process. If your eventsourcing application object has
any policies, for example if is has a persistence policy that will
persist events whenever they are published, then constructing more
than one instance of the application causes the policy event handlers
to be subscribed more than once, so for example more than one attempt
will be made to save each event, which won't work.

To make sure there is only one instance of your application object in
each process, one possible arrangement (see below) is to have a module
with two functions and a variable. The first function constructs an
application object and assigns it to the variable, and can perhaps be
called when a module is imported, or from a suitable hook or signal
designed for setting things up before any requests are handled. A
second function returns the application object assigned to the variable,
and can be called by any views, or request or task handlers, that depend
on the application's services.

Although the first function below must be called only once, the second
function can be called many times. The example functions below have
been written relatively strictly so that, when it is called, the function
``init_application()`` will raise an exception if it has already been
called, and ``get_application()`` will raise an exeception if
``init_application()`` has not already been called.

.. code:: python

    # Your eventsourcing application.
    class ExampleApplication(object):
        def __init__(*args, **kwargs):
            pass


    def construct_application(**kwargs):
        return ExampleApplication(**kwargs)


    _application = None


    def init_application(**kwargs):
        global _application
        if _application is not None:
            raise AssertionError("init_application() has already been called")
        _application = construct_application(**kwargs)


    def get_application():
        if application is None:
            raise AssertionError("init_application() must be called first")
        return application


As an aside, if you will use these function also in your test suite, and your
test suite needs to set up the application more than once, you will also need
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


Lazy initialization
-------------------

An alternative to having separate "init" and "get" functions is having one
"get" function that does lazy initialization of the application object when
first requested. With lazy initialization, the getter will first check if
the object it needs to return has been constructed, and will then return the
object. If the object hasn't been constructed, before returning the object
it will construct the object. So you could use a lock around the construction
of the object, to make sure it only happens once. After the lock is obtained
and before the object is constructed, it is recommended to check again that
the object wasn't constructed by another thread before the lock was acquired.

.. code:: python

    import threading

    application = None

    lock = threading.Lock()

    def get_application():
        global application
        if application is None:
            lock.acquire()
            try:
                # Check again to avoid a TOCTOU bug.
                if application is None:
                    application = construct_application()
            finally:
                lock.release()
        return application



Database connection
===================

Typically, your eventsourcing application object will be constructed after
its database connection has been configured, and before any requests are handled.
Views or tasks can then safely use the already constructed application object.

If your eventsourcing application depends on receiving a database session
object when it is constructed, for example if you are using the SQLAlchemy
classes in this library, then you will need to create a correctly scoped
session object first and use it to construct the application object.

On the other hand, if your eventsourcing application does not depend on
receiving a database session object when it is constructed, for example if
you are using the Cassandra classes in this library, then you may construct
the application object before configuring the database connection - just be
careful not to use the application object before the database connection is
configured otherwise your queries just won't work.

Setting up connections to databases is out of scope of the eventsourcing
application classes, and should be set up in a "normal" way. The documentation
for your Web or worker framework may describe when to set up database connections,
and your database documentation may also have some suggestions. It is recommended
to make use of any hooks or decorators or signals intended for the purpose of setting
up the database connection also to construct the application once for the process.
See below for some suggestions.


SQLAlchemy
----------

SQLAlchemy has `very good documentation about constructing sessions
<http://docs.sqlalchemy.org/en/latest/orm/session_basics.html>`__.
If you are an SQLAlchemy user, it is well worth reading the
documentation about sessions in full. Here's a small quote:

.. pull-quote::

    *Some web frameworks include infrastructure to assist in the task of aligning
    the lifespan of a Session with that of a web request. This includes products
    such as Flask-SQLAlchemy for usage in conjunction with the Flask web framework,
    and Zope-SQLAlchemy, typically used with the Pyramid framework. SQLAlchemy
    recommends that these products be used as available.*

    *In those situations where the integration libraries are not provided or are
    insufficient, SQLAlchemy includes its own “helper” class known as scoped_session.
    A tutorial on the usage of this object is at Contextual/Thread-local Sessions. It
    provides both a quick way to associate a Session with the current thread, as well
    as patterns to associate Session objects with other kinds of scopes.*

The important thing is to use a scoped session, and it is better
to have the session scoped to the request or task, rather than
the thread, but scoping to the thread is ok.

As soon as you have a scoped session object, you can construct
your eventsourcing application.


Cassandra
---------

Cassandra connections can be set up entirely independently of the application
object. See the section about :doc:`using Cassandra</topics/user_guide/cassandra>`
for more information.


Web interfaces
==============

uWSGI
-----

If you are running uWSGI in prefork mode, and not using a Web application framework,
please note that uWSGI has a `postfork decorator
<http://uwsgi-docs.readthedocs.io/en/latest/PythonDecorators.html#uwsgidecorators.postfork>`__
which may help.

Your "wsgi.py" file can have a module-level function decorated with the ``@postfork``
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


Flask with Cassandra
--------------------

The `Cassandra Driver FAQ <https://datastax.github.io/python-driver/faq.html>`__
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


Flask-SQLAlchemy
----------------

If you wish to use eventsourcing with Flask and SQLAlchemy, then you may wish
to use `Flask-SQLAlchemy <http://flask-sqlalchemy.pocoo.org/>`__.
You just need to define your active record class
using the model classes from that library, and then use it instead of the
library classes in your eventsourcing application object, along with the
session object it provides.

The docs snippet below shows that it can work simply to construct
the eventsourcing application in the same place as the Flask
application object.

The Flask-SQLAlchemy class `SQLAlchemy` is used to set up a session
object that is scoped to the request.

.. code:: python

    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy
    from sqlalchemy_utils.types.uuid import UUIDType
    from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy


    # Construct Flask application.
    application = Flask(__name__)

    # Construct Flask-SQLAlchemy object.
    db = SQLAlchemy(application)

    # Define database table using Flask-SQLAlchemy library.
    class IntegerSequencedItem(db.Model):
        __tablename__ = 'integer_sequenced_items'

        # Sequence ID (e.g. an entity or aggregate ID).
        sequence_id = db.Column(UUIDType(), primary_key=True)

        # Position (index) of item in sequence.
        position = db.Column(db.BigInteger(), primary_key=True)

        # Topic of the item (e.g. path to domain event class).
        topic = db.Column(db.String(255))

        # State of the item (serialized dict, possibly encrypted).
        data = db.Column(db.Text())

        # Index.
        __table_args__ = db.Index('index', 'sequence_id', 'position'),


    # Construct eventsourcing application with db table and session.
    init_application(
        entity_active_record_strategy=SQLAlchemyActiveRecordStrategy(
            active_record_class=IntegerSequencedItem,
            session=db.session,
        )
    )


For a working example using Flask and SQLAlchemy, please
refer to the library module :mod:`eventsourcing.example.interface.flaskapp`,
which is tested both stand-alone and with uWSGI.
The Flask application method "before_first_request" is used to decorate an
application object constructor, just before a request is made, so that the
module can be imported by the test suite, without immediately constructing
the application.


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


Zope-SQLAlchemy
---------------

The `Zope-SQLAlchemy <https://pypi.python.org/pypi/zope.sqlalchemy>`__
project serves a similar function to Flask-SQLAlchemy.


Task queues
===========

This section contains suggestions about using an eventsourcing application in task queue workers.


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


Once the application has been safely initialized once
in the process, your Celery tasks can use function ``get_application()``
to complete their work. Of course, you could just call a getter with lazy
initialization from the tasks.

.. code:: python

    from celery import Celery

    app = Celery()

    # Use Celery app to route the task to the worker.
    @app.task
    def hello_world():
        # Use eventsourcing app to complete the task.
        app = get_application()
        return "Hello World, {}".format(id(app))


Again, the most important thing is configuring the database, and making
things work across all modes of execution, including your test suite.


Redis Queue
-----------

Redis `queue workers <http://python-rq.org/docs/workers/>`__ are
quite similar to Celery workers. You can call ``get_application()``
from within a job function. To fit with the style in the RQ
documentation, you could perhaps use your eventsourcing application
as a context manager, just like the Redis connection example.
