============
Installation
============

Use pip to install the library from the
`Python Package Index <https://pypi.org/project/eventsourcing/>`__.

::

    $ pip install eventsourcing


If you want to use `SQLAlchemy <https://www.sqlalchemy.org/>`__, then install
the library with the 'sqlalchemy' option. Also install your chosen
`database driver <http://docs.sqlalchemy.org/en/latest/core/engines.html#database-urls>`__.

::

    $ pip install eventsourcing[sqlalchemy]
    $ pip install psycopg2


Similarly, if you want to use `Apache Cassandra <http://cassandra.apache.org/>`__,
then please install with the 'cassandra' option.

::

    $ pip install eventsourcing[cassandra]


Running the install command with again different options will just install
the extra dependencies associated with that option. If you installed
without any options, you can easily install optional dependencies
later by running the install command again with the options you want.
