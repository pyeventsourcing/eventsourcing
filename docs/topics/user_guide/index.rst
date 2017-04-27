==========
User guide
==========

This guide describes how to write an event sourced application,
using classes in this library.

In the first section, a stand-alone event sourced domain model is
developed, along with an application object that has minimal
dependencies on library infrastructure classes for storing events.
In later sections, more use is made of library classes, in order
to introduce the other capabilities of the library.

All the examples in this guide follow the layered architecture:
application, domain, infrastructure. To create working programs,
simply copy all the code snippets from a section into a Python file.

Please feel free to experiment by making variations. The code snippets
are extracted and executed by a test case in the library's test suite,
so please expect everything to work as presented (raise an issue if
something goes wrong).


.. toctree::
   :maxdepth: 2
   :caption: Contents


   quick_start
   example_application
   snapshotting
   aggregates_in_ddd
   encryption
   concurrency
   schema
   cassandra
   wsgi
