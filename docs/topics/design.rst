======
Design
======

The design of the library follows the layered architecture: interfaces,
application, domain, and infrastructure.

The domain layer contains a model of the supported domain, and services
that depend on that model. The infrastructure layer encapsulates the
infrastructural services required by the application.

The application is responsible for binding domain and infrastructure,
and has policies such as the persistence policy, which stores domain
events whenever they are published by the model.

The example application has an example respository, from which example
entities can be retrieved. It also has a factory method to register new
example entities. Each repository has an event player, which all share
an event store with the persistence policy. The persistence policy uses
the event store to store domain events, and the event players use the
event store to retrieve the stored events. The event players also share
with the model the mutator functions that are used to apply domain
events to an initial state.

Functionality such as mapping events to a database, or snapshotting, is
factored as strategy objects and injected into dependents by constructor
parameter. Application level encryption is a mapping option.

The sequenced item persistence model allows domain events to be stored
in wide variety of database services, and optionally makes use of any
optimistic concurrency controls the database system may afford.

.. figure:: https://www.lucidchart.com/publicSegments/view/098200e1-0ca9-4660-be7f-11f8f13a2163/image.png
   :alt: UML Class Diagram
