==========
User Guide
==========

.. toctree::
   :maxdepth: 2

   example_application
   snapshotting
   encryption
   concurrency
   schema
   aggregates
   cassandra



This user guide describes how to write an event sourced application.

To create a working program, you can copy and paste the following code
snippets into a single Python file. The code snippets in this section
have been tested. Please feel free to experiment by making variations.

If you are using a Python virtualenv, please check that your virtualenv
is activated before installing the library and running your program.

Install the library with the 'sqlalchemy' and 'crypto' options.

::

    pip install eventsourcing[sqlalchemy,crypto]

