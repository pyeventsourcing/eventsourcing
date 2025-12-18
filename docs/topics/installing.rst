============
Installation
============

This version of the library is compatible with Python versions 3.10,
3.11, 3.12, 3.13, and 3.14.

This package depends only on modules from the Python Standard Library,
except for ``typing_extensions`` and the extra install options described below.


Pip install
===========

You can use pip to install the library from the
`Python Package Index <https://pypi.org/project/eventsourcing/>`_.

::

    $ pip install eventsourcing

It is recommended to install the library into a Python virtual environment.

::

    $ python3 -m venv my_venv
    $ source my_venv/bin/activate
    (my_venv) $ pip install eventsourcing


Assuming you are developing a true application (and not a library), when including this library
in your list of project dependencies, in order to avoid installing future incompatible releases,
it is recommended to specify the major and minor version numbers, use dependency locking, and walk
the dependency forward in a controlled way. Please note, it is recommended to test all updates in
your CI.

As an example, the expression ``eventsourcing~=9.5.0b3`` would install the latest version of
the 9.5 series, allowing future bug fixes released with point version increments, whilst avoiding
any changes introduced by major and minor version increments that might break your code. You can use
this expression in a ``pip install`` command.

::

    $ pip install "eventsourcing~=9.5.0b3"

You can use the same expression in ``requirements.txt`` files, in ``setup.py`` files, and
in ``pyproject.toml`` files.

For example, if you are specifying the dependencies of your project in a ``pyproject.toml``
file, you can specify the dependency on this library in the following way.

::

    [project]
    requires-python = ">=3.10"
    dependencies = [
        "eventsourcing~=9.5.0b3",
    ]


Requiring a specific major and minor version number in this way will avoid any
potentially destabilising additional features with minor version increments, and
also avoid potentially backward incompatible changes introduced with major version
number increments.

Upgrading to new versions is encouraged, but it is recommended to do this carefully
so that you can be sure your project isn't inadvertently broken by changes in the library.

Please note, if you are developing a library that depends on this library, then it is
generally recommended not to have upper limit caps on the versions of your dependencies,
and to leave the responsibility for ensuring application integrity to application developers.

Install options
===============

Running the install command with different options will install
the extra dependencies associated with that option. If you installed
without any options, you can easily install optional dependencies
later by running the install command again with the options you want.

If you want to :ref:`store events with PostgreSQL <postgres-environment>`, then install with
the ``postgres`` option. This installs `Psycopg v3 <https://pypi.org/project/psycopg/>`_
and its connection pool package.

The C optimization is recommended by the `Psycopg <https://www.psycopg.org>`_  developers for production usage.
The pre-built binary option ``psycopg[binary]`` is a convenient alternative for development and testing, and
for those unable to meet the prerequisites needed for building ``psycopg[c]``.

This package now follows the recommendation that libraries should depend only on the pure Python package, giving
users the choice of either compiling the C optimization or using the pre-built binary or using the pure
Python package. If you don't install either ``psycopg[c]`` or ``psycopg[binary]`` then you need to make sure
libpq is installed (libpq is the client library used by psql, the PostgreSQL command line client). See
the `Psycopg docs <https://www.psycopg.org/psycopg3/docs/basic/install.html#pure-python-installation>`_ for more
information.

See the :ref:`PostgreSQL persistence module documentation <postgres-environment>` for more information about storing
events in PostgreSQL.

::

    $ pip install "eventsourcing[postgres]"


If you want to store cryptographically encrypted events,
then install with the ``cryptography`` option. This simply installs
the Python `cryptography <https://pypi.org/project/cryptography/>`_ package.
Please note, you will need to :ref:`configure your application <Application configuration>`
environment to enable encryption.

::

    $ pip install "eventsourcing[cryptography]"


Alternatively, if you want to store cryptographically encrypted events,
then you can install with the ``crypto`` option. This simply installs
`PyCryptodome <https://pypi.org/project/pycryptodome/>`_.
Please note, you will need to :ref:`configure your application <Application configuration>`
environment to enable encryption.

::

    $ pip install "eventsourcing[crypto]"


Options can be combined, so that if you want to store encrypted events in PostgreSQL,
then install with both the ``postgres`` and the ``cryptography`` options.

::

    $ pip install "eventsourcing[postgres,cryptography]"


.. _Template:

Project template
================

To start a new project with modern tooling, you can use the
`template for Python eventsourcing projects <https://github.com/pyeventsourcing/cookiecutter-eventsourcing#readme>`_.

The project template uses Cookiecutter to generate project files.
It uses the build tool Poetry to create Python virtual environments
for your project, to manage project dependencies, and to create distributions.
It uses popular development dependencies such as pytest, coverage, Black,
isort, and mypy to help you develop and maintain your code. It has a GitHub
Actions workflow, and has an initial README and LICENCE files that you
can adjust.

The project template also includes the "dog school" example. The tests
should pass. You can adjust the tests, rename the classes, and change the
methods. Or just delete the included example code for a fresh start.


Developers
==========

If you want to install the code for the purpose of developing the library, then
fork and clone the GitHub repository.

Once you have cloned the project's GitHub repository, change into the root folder,
or open the project in an IDE. You should see a Makefile.

If you don't already have the required version of Poetry installed, running
``make install-poetry`` will install it with pipx, using a suffix to indicate
the version e.g. ``poetry@2.2.1``.

::

    $ make install-poetry


Run ``make install`` to create a new virtual environment and install packages that
are needed for development, such as sphinx, coverage, black, ruff, isort, mypy,
and pyright.

::

    $ make install


Once installed, check the project's test suite passes by running ``make test``.

::

    $ make test


Before the tests will pass, you will need to set up PostgreSQL, with a database
called 'eventsourcing' that can be accessed by a user called 'eventsourcing'
that has password 'eventsourcing'.

The following commands will install PostgreSQL on MacOS and set up the database and
database user. If you already have PostgreSQL installed, just create the database
and user. You may prefer to run PostgreSQL in a Docker container.

::

    $ brew install postgresql
    $ brew services start postgresql
    $ psql postgres
    postgres=# CREATE DATABASE eventsourcing;
    postgres=# CREATE USER eventsourcing WITH PASSWORD 'eventsourcing';
    postgres=# ALTER DATABASE eventsourcing OWNER TO eventsourcing;
    $ psql eventsourcing
    postgres=# CREATE SCHEMA myschema AUTHORIZATION eventsourcing;


The code can be automatically reformatted using the following command
(which uses isort and Black). Ruff and mypy errors will often need
to be fixed by hand.

::

    $ make fmt


Check the syntax and static types are correct by running ``make lint``.

::

    $ make lint


You can build the docs (and check they build) with ``make docs``.

::

    $ make docs

You can update the locked package dependencies and install them with ``make update``.

::

    $ make update

You can make sure everything is okay by running ``make install docs fmt lint test benchmark``.

::

    $ make install docs lint test benchmark

Or more simply, run ``make all``:

::

    $ make all

Or more simply ``make``:

::

    $ make
