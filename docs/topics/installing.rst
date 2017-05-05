============
Installation
============

Use pip to install the library from the
`Python Package Index <https://pypi.python.org/pypi/eventsourcing>`__.

::

    pip install eventsourcing


If you want to use SQLAlchemy, then please install the library with the 'sqlalchemy' option.

::

    pip install eventsourcing[sqlalchemy]


Similarly, if you want to use Cassandra, please install with the 'cassandra' option.

::

    pip install eventsourcing[cassandra]


If you want to use encryption, please install with the 'crypto' option.

::

    pip install eventsourcing[crypto]


You can install combinations of options at the same time, for exampe the follow
command will install dependencies for Cassandra and for encryption.

::

    pip install eventsourcing[cassandra,crypto]

Running the install command with different options will just install
the extra dependencies associated with that option. If you installed
without any options, you can easily install optional dependencies
later by running the install command again with the options you want.
