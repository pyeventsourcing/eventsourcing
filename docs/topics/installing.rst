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


Install options
===============

Running the install command with different options will install
the extra dependencies associated with that option. If you installed
without any options, you can easily install optional dependencies
later by running the install command again with the options you want.

For example, if you want to store cryptographically encrypted events,
then install with the ``crypto`` option.

::

    $ pip install eventsourcing[crypto]


If you want to store events with PostgreSQL, then install with
the ``postgres`` option.

::

    $ pip install eventsourcing[postgres]


Options can be combined, so that if you want to store encrypted events in PostgreSQL,
then install with the ``crypto`` and ``postgres`` options.

::

    $ pip install eventsourcing[crypto,postgres]


Developers
----------

If you want to install the code for development, then clone the GitHub repository
and install from the root folder with the 'dev' option.

::

    $ pip install .[dev]
