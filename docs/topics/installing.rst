==================
Installation guide
==================

It is recommended always to install into a virtual environment.

You can use pip to install the library from the
`Python Package Index <https://pypi.org/project/eventsourcing/>`__.

::

    $ pip install eventsourcing


Other package installers are available.

To avoid installing future incompatible releases, when including the
library in a list of project dependencies it is recommended to specify
at least some of the current version number. Preferences regarding how
and where to specify versions of project dependencies vary.

::

    eventsourcing<=8.2.99999

As an example, the expression above would install the latest version
of v8.2.x series of releases, allowing future bug fixes to be installed
with point version number increments, whilst avoiding any potentially
destabilising additional features introduced with minor version number
increments, and also any backwards incompatible changes introduced with
major verison number increments.


Install options
===============

Running the install command with again different options will just install
the extra dependencies associated with that option. If you installed
without any options, you can easily install optional dependencies
later by running the install command again with the options you want.


SQLAlchemy
----------

If you want to store events using `SQLAlchemy <https://www.sqlalchemy.org/>`__, then install
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

Similarly, if you want to store events using `Django <https://www.djangoproject.com/>`__,
then please install with the 'django' option.

::

    $ pip install eventsourcing[django]

You can use Django with SQLite, in which case you don't need to install
any database driver. Otherwise please also install a database driver
that works with `Django and your database system <https://docs.djangoproject.com/en/2.2/ref/databases/>`__.


Cassandra
---------

If you want to store events using `Apache Cassandra <http://cassandra.apache.org/>`__,
then please install with the 'cassandra' option.

::

    $ pip install eventsourcing[cassandra]


Ray
---

If you want to run a system of applications with `Ray <https://ray.io/>`__,
then please install with the 'ray' option.

::

    $ pip install eventsourcing[ray]



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
