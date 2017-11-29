======
Design
======

The design of the library follows the layered architecture: interfaces,
application, domain, and infrastructure.

The infrastructure layer encapsulates infrastructural services
required by an event sourced application, in particular an event
store.

The domain layer contains independent domain model classes. Nothing
in the domain layer depends on anything in the infrastructure layer.

The application layer is responsible for binding domain and infrastructure,
and has policies such as the persistence policy, which stores domain
events whenever they are published by the model.

The example application has an example repository, from which example
entities can be retrieved. It also has a factory method to create new
example entities. Each repository has an event player, which all share
an event store with the persistence policy. The persistence policy uses
the event store to store domain events. Event players use the
event store to retrieve the stored events, and the model mutator functions
to project entities from sequences of events.

Functionality such as mapping events to a database, or snapshotting, is
implemented as strategy objects, and injected into dependents by constructor
parameter, making it easy to substitute custom classes for defaults.

The sequenced item persistence model allows domain events to be stored
in wide variety of database services, and optionally makes use of any
optimistic concurrency controls the database system may afford.

.. figure:: https://www.lucidchart.com/publicSegments/view/098200e1-0ca9-4660-be7f-11f8f13a2163/image.png
   :alt: UML Class Diagram
