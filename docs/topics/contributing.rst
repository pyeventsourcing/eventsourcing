============
Contributing
============

This library depends on its community. As interest keeps growing, we always need more people to help
others. As soon as you learn the library, you can contribute in many ways.

- Join the Slack_ channel and answer questions. The library has a growing audience. Help to create
  and maintain a friendly and helpful atmosphere.

- Blog and tweet about the library. If you would like others to see your blog or tweet, send a
  message about it to the Slack_ channel.

- Contribute to open-source projects that use this library, write some documentation, or release
  your own event sourcing project.


.. _Slack: https://join.slack.com/t/eventsourcinginpython/shared_invite/enQtMjczNTc2MzcxNDI0LTJjMmJjYTc3ODQ3M2YwOTMwMDJlODJkMjk3ZmE1MGYyZDM4MjIxODZmYmVkZmJkODRhZDg5N2MwZjk1YzU3NmY>`__.


If you think using the library is a lot of fun, wait until you start working on it. We’re passionate
about helping users of the library make the jump to contributing members of the community, so there
are several ways you can help the library’s development:

- Report bugs on our `issue tracker <https://github.com/johnbywater/eventsourcing/issues>`__.
- Join the Slack_ channel and share your ideas for how to improve the library. We’re always
  open to suggestions.
- Submit patches or pull requests for new and/or fixed behavior.
- Improve the documentation or write unit tests.


Local development
=================

This library using `GNU make`_ utility and multiple python packages for code linting. You can read more
about it at `this article`_. The actual code of the provided commands below can be easily found and read in
`Makefile` at the root of this project. But first, you need to set up your local development environment.

.. _GNU make: https://www.gnu.org/software/make/
.. _this article: https://opensource.com/article/18/8/what-how-makefile


.. _development-environment:

Configure the development environment
=====================================

This project runs on Python 3.6+, and you need to have it installed on your system.
The recommended way for all platforms is to use the `official download page`_.
But also, you may use pyenv_.

.. _official download page: https://www.python.org/downloads/
.. _pyenv: https://github.com/pyenv/pyenv

Consider to use virtualenv for development, choose for your flavor:

- virtualenvwrapper_
- pyenv-virtualenv_ for pyenv_

.. _virtualenvwrapper: https://virtualenvwrapper.readthedocs.io/en/latest/
.. _pyenv-virtualenv: https://github.com/pyenv/pyenv-virtualenv

Use the following command inside your activated virtualenv to install all project dependencies
required for contribution::

    make install


.. _docker-containers:

Manage Docker containers
========================

You need to manage Docker containers with third-party services to have a better experience with local development.
To pull docker images::

    make docker-pull

To up and keep running containers in detached mode::

    make docker-up

To stop the containers::

    make docker-stop

To tear down the containers removing volumes and “orphans”::

    make docker-down

To attach to the latest containers output::

    make docker-logs

All of the commands using predefined “COMPOSE_FILE “and “COMPOSE_PROJECT_NAME “to keep
your containers in a more organized and straightforward way.

**COMPOSE_FILE** is used by *docker-compose* utility to pick development services
configuration. The valid format of this value is: ``dev/docker-compose.yaml “.

**COMPOSE_PROJECT_NAME** sets the project name. This value used to prepend the
containers on startup along with the service name. “eventsourcing “is a great default value for it.


Testing
=======

Ensure that you’ve set up your development environment (see :ref:`development-environment`) and
and required services are up and running (see :ref:`docker-containers`).

Just run this::

    make test

.. note::
    Not all tests doing teardown in the right way: sometimes tests failed because of the
    data left at DBs, so it requires ``make docker-down`` for a fresh start.

... or push the code to trigger TravisCI checks.


Building documentation
======================

This project using Sphinx_ documentation builder tool. Run this command to compile documentation
into static HTML files at `./docs/_build/html`::

    make docs

.. _Sphinx: https://www.sphinx-doc.org/en/master/
