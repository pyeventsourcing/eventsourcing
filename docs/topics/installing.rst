==================
Installation guide
==================

Use pip to install the library from the
`Python Package Index <https://pypi.org/project/eventsourcing/>`__.

::

    $ pip install eventsourcing


Install options
===============

Running the install command with again different options will just install
the extra dependencies associated with that option. If you installed
without any options, you can easily install optional dependencies
later by running the install command again with the options you want.


SQLAlchemy
----------

If you want to use `SQLAlchemy <https://www.sqlalchemy.org/>`__, then install
the library with the 'sqlalchemy' option.

::

    $ pip install eventsourcing[sqlalchemy]

You can use SQLAlchemy with SQLite, in which case you don't need to install
any database driver. Otherwise please also install a `database driver
<http://docs.sqlalchemy.org/en/latest/core/engines.html#database-urls>`__
that works with SQLAlchemy and your database system.

::

    $ pip install psycopg2-binary  # for PostgreSQL
    $ pip install pymysql          # for MySQL

See the  :doc:`Infrastructure doc </topics/infrastructure>` for more information
about crafting database connection strings for particular database drivers.


Django
------

Similarly, if you want to use `Django <https://www.djangoproject.com/>`__,
then please install with the 'django' option.

::

    $ pip install eventsourcing[django]

You can use Django with SQLite, in which case you don't need to install
any database driver. Otherwise please also install a database driver
that works with `Django and your database system <https://docs.djangoproject.com/en/2.2/ref/databases/>`__.


Cassandra
---------

If you want to use `Apache Cassandra <http://cassandra.apache.org/>`__,
then please install with the 'cassandra' option.

::

    $ pip install eventsourcing[cassandra]


Tests
-----

If you want to run the tests, then please install with the 'tests' option.

::

    $ pip install eventsourcing[tests]


Docs
----

If you want build the docs, then please install with the 'docs' option.

::

    $ pip install eventsourcing[docs]
