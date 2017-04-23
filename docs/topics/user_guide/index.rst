==========
User Guide
==========

This guide describes how to write an event sourced application
using classes in this library. At first a stand-alone domain
model is developed, and an application with minimal dependencies
on the library infrastructure classes for storing events. In later
sections, more use is made of library classes, in order to introduce
the other capabilities of the library.

All the examples in this guide follow the layered architecture:
application, domain, infrastructure. To create a working program,
simply copy all the code snippets from a section into a Python file.

Please feel free to experiment by making variations. The code snippets
are executed by a test in the library's test suite, so please expect
everything to work as presented (raise an issue if something goes wrong).


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
