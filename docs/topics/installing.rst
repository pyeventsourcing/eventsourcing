============
Installation
============

This version of the library is compatible with Python 3.11, 3.12, 3.13, and 3.14.

The package depends only on modules from the Python Standard Library,
with the exception of ``typing_extensions`` and any optional extras described below.

Installing the Package
======================

You can install ``eventsourcing`` from the `Python Package Index (PyPI) <https://pypi.org/project/eventsourcing/>`_
using your preferred package manager.

With uv:

.. code-block:: bash

    uv add "eventsourcing"

With Poetry:

.. code-block:: bash

    poetry add "eventsourcing"

With pipenv:

.. code-block:: bash

    pipenv add "eventsourcing"

With pip (via virtual environment):

.. code-block:: bash

    python3 -m venv .venv
    source .venv/bin/activate
    pip install "eventsourcing"

Dependency Management
=====================

How you declare this library as a dependency depends on the type of project you are building.

For Applications
----------------
If you are developing an application, we recommend pinning the major and minor version numbers. This allows you to receive backwards-compatible bug fixes while protecting your codebase from potentially breaking changes introduced in major or minor releases.

You can achieve this using the compatible release operator (``~=``). For example, ``eventsourcing~=10.0.0`` installs the latest point release in the 10.0 series.

Example ``pyproject.toml`` configuration:

.. code-block:: toml

    [project]
    requires-python = ">=3.11"
    dependencies = [
        "eventsourcing~=10.0.0",
    ]

For Libraries
-------------
If you are developing a library that depends on ``eventsourcing``, it is generally best practice to avoid strict upper version bounds. Leave the responsibility of version pinning and dependency locking to the downstream application developers.

Best Practices
--------------
Regardless of your project type, we strongly encourage you to:

* Use dependency locking (e.g., ``uv.lock``, ``poetry.lock``, ``Pipfile.lock``, or locked ``requirements.txt`` files).
* Update dependencies systematically.
* Test all updates thoroughly in your Continuous Integration (CI) pipeline.

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


If you want to use the library's Pydantic domain model classes,
then you can install with the ``pydantic`` option. This simply installs
`Pydantic <https://pydantic.dev/docs/validation/latest/get-started>`_.

::

    $ pip install "eventsourcing[pydantic]"


If you want to use the library's msgspec domain model classes,
then you can install with the ``msgspec`` option. This simply installs
`msgspec <https://msgspec.dev>`_.

::

    $ pip install "eventsourcing[msgspec]"


Options can be combined, so that if you want to store encrypted Pydantic events in PostgreSQL,
then install with the ``cryptography``, ``pydantic`` and ``postgres`` options.

::

    $ pip install "eventsourcing[cryptography,postgres,pydantic]"


.. _Template:


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
