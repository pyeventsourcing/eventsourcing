==========
User Guide
==========

This guide describes how to write an event sourced application.

All the examples in this guide follow the layered architecture:
application, domain, infrastructure. To create a working program,
simply copy all the code snippets from a section into a Python file.

Please feel free to experiment by making variations. The code snippets
are tested automatically by the library's test suite, so everything should
just work.


.. toctree::
   :maxdepth: 3

   example_application
   encryption
   concurrency
   snapshotting
   aggregates
   schema
   cassandra
   wsgi
