============
Installation
============

This version of the library is compatible with Python versions 3.7, 3.8,
3.9, 3.10, and 3.11. The library's suite of tests is run against these
versions and has 100% line and branch coverage.

This package depends only on modules from the Python Standard Library,
except for the extra install options described below.

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


When including the library in a list of project dependencies, in order to
avoid installing future incompatible releases, it is recommended to specify
the major and minor version numbers.

As an example, the expression ``eventsourcing<=9.2.99999`` would install the
latest version of the 9.2 series, allowing future bug fixes released with
point version number increments. You can use this expression in a ``pip install``
command, in a ``requirements.txt`` file, or in a ``setup.py`` file.

::

    $ pip install "eventsourcing<=9.2.99999"

If you are specifying the dependencies of your project in a ``pyproject.toml``
file, and for example using the Poetry build tool, you can specify the
dependency on this library in the following way.

::

    [tool.poetry.dependencies]
    python = "^3.8"
    eventsourcing = { version = "~9.2.0" }


Specifying the major and minor version number in this way will avoid any
potentially destabilising additional features introduced with minor version
number increments, and also avoid all backward incompatible changes introduced
with major version number increments.

Upgrading to new minor versions is encouraged, but it is recommended to
do this manually so that you are sure your project isn't inadvertently
broken by changes in the library. Migrating to new major versions is
also encouraged, but by definition this may involve your making changes
to your project to adjust for the backward incompatibilities introduced
by the new major version. Of course it's your project so, if you wish,
feel free to pin the major and minor and point version, or indeed only
the major version.

Install options
===============

Running the install command with different options will install
the extra dependencies associated with that option. If you installed
without any options, you can easily install optional dependencies
later by running the install command again with the options you want.
You can also make your project depend directly on the extra dependencies.

For example, if you want the option to store cryptographically encrypted
events, then install with the ``crypto`` option. This simply installs
`PyCryptodome <https://pypi.org/project/pycryptodome/>`_
so feel free to make your project directly depend on that package.
After installing this package, you will need to
:ref:`configure your application <Application configuration>`
environment to enable encryption.

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


.. _Template:

Project template
================

To start a new project with modern tooling, you can use the
`template for Python eventsourcing projects <https://github.com/pyeventsourcing/cookiecutter-eventsourcing#readme>`_.

The project template uses Cookiecutter to generate project files.
It uses the build tool Poetry to create a Python virtual environments
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
fork and clone the GitHub repository and install into a Python virtual environment
from the root folder with the 'dev' option. This option will install a number of
packages that help with development and documentation, such as the above extra
dependencies along with Sphinx, Coverage.py, Black, mypy, Flake8, and isort.

::

    $ pip install -U pip
    $ pip install wheel
    $ pip install -e ".[dev]"

Alternatively, the project's Makefile can be used to the same effect with
the following command.

::

    $ make install


Once installed, you can check the unit tests pass and the code is 100% covered
by the tests with the following command.

::

    $ make test


Before the tests will pass, you will need setup PostgreSQL. The following commands
will install PostgreSQL on MacOS and setup the database and database user. If you
already have PostgreSQL installed, just create the database and user. If you prefer
to run PostgreSQL in a Docker container, feel free to do that too.

::

    $ brew install postgresql
    $ brew services start postgresql
    $ psql postgres
    postgres=# CREATE DATABASE eventsourcing;
    postgres=# CREATE USER eventsourcing WITH PASSWORD 'eventsourcing';
    postgres=# ALTER DATABASE eventsourcing OWNER TO eventsourcing;
    $ psql eventsourcing
    postgres=# CREATE SCHEMA myschema AUTHORIZATION eventsourcing;


You can also check the syntax and static types are correct with the
following command (which uses isort, Black, Flake8, and mypy).

::

    $ make lint


The code can be automatically reformatted using the following command
(which uses isort and Black). Flake8 and mypy errors will often need
to be fixed by hand.

::

    $ make fmt


You can build the docs, and make sure they build, with the following command
(which uses Sphinx).

::

    $ make docs


If you wish to submit changes to the library, before submitting a pull
request please check all three things (lint, docs, and test) which you
can do conveniently with the following command.

::

    $ make prepush

If you wish to submit a pull request on GitHub, please target the main
branch. Improvements of any size are always welcome.
