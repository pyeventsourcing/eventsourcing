============
Installation
============

Use pip to install the library from the
`Python Package Index <https://pypi.python.org/pypi/eventsourcing>`__.

::

    pip install -U pip
    pip install eventsourcing

If you want to use SQLAlchemy, then please install the library  with the 'sqlalchemy' option.

::

    pip install eventsourcing[sqlalchemy]

Similarly, if you want to use Cassandra, then please install the library with the
'cassandra' option.

::

    pip install eventsourcing[cassandra]

If you want to run the test suite, then please install with the 'test' option.

::

    pip install eventsourcing[test]

After installing with 'test', and installing Cassandra locally, the test
suite should pass.

::

    python -m unittest discover eventsourcing.tests -v

Please register any `issues on
GitHub <https://github.com/johnbywater/eventsourcing/issues>`__.

There is also a `mailing
list <https://groups.google.com/forum/#!forum/eventsourcing-users>`__.
And a `room on
Gitter <https://gitter.im/eventsourcing-in-python/eventsourcing>`__
