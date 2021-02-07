==================
Installation guide
==================

It is recommended always to install into a virtual environment.

You can use pip to install the library from the
`Python Package Index <https://pypi.org/project/eventsourcing/>`__.

::

    $ pip install eventsourcing

When including the library in a list of project dependencies, in order to
avoid installing future incompatible releases, it is recommended to specify
the major and minor version numbers.

As an example, the expression below would install the latest version of the
v9.0.x release, allowing future bug fixes released with point version number
increments.

::

    eventsourcing<=9.0.99999

Specifying the major and minor version number in this way will avoid any
potentially destabilising additional features introduced with minor version
number increments, and also any backwards incompatible changes introduced
with major version number increments.

This package depends only on modules from the Python Standard Library,
except for the extra options described below.


Install options
===============

Running the install command with different options will install
the extra dependencies associated with that option. If you installed
without any options, you can easily install optional dependencies
later by running the install command again with the options you want.

For example, if you want to store cryptographically encrypted events,
then install with the ``crypto`` option. This simply installs
`Pycryptodome <https://pypi.org/project/pycryptodome/>`_
so feel free to make your project depend on that instead.

::

    $ pip install "eventsourcing[crypto]"


If you want to store events with PostgreSQL, then install with
the ``postgres`` option. This simply installs
`Psycopg2 <https://pypi.org/project/psycopg2/>`_ so feel
free to make your project depend on that instead. Please note,
the binary version `psycopg2-binary <https://pypi.org/project/psycopg2-binary/>`_
is a convenient alternative for development and testing, but the main
package is recommended by the Psycopg2 developers for production usage.

::

    $ pip install "eventsourcing[postgres]"


Options can be combined, so that if you want to store encrypted events in PostgreSQL,
then install with the ``crypto`` and ``postgres`` options.

::

    $ pip install "eventsourcing[crypto,postgres]"


Developers
==========

If you want to install the code for the purpose of developing the library, then
fork and clone the GitHub repository and install from the root folder with the
'dev' option. This option will install a number of packages that help with
development and documentation, such as the above extra dependencies along with
Sphinx, Coverage.py, Black, mypy, Flake8, and isort.

::

    $ pip install ".[dev]"

Alternatively, the project's Makefile can be used to the same effect.

::

    $ make install


Once installed, you can check the unit tests pass and the code is 100% covered
by the tests with the following command.

::

    $ make test


You can also check the syntax and static types are correct with the following command.

::

    $ make lint


You can also make sure the docs build with the following command.

::

    $ make docs


If you wish to submit changes to the library, before submitting a pull
request please check all three things (test, lint, and docs) which
you can do conveniently with the following command.

::

    $ make prepush
