======
Design
======

The design of the library follows "layered architecture" in that there
are distinct and separate layers for interfaces, application, domain and
infrastructure. It also follows the "onion" or "hexagonal" or "clean"
architecture, in that the domain layer has no dependencies any other
layer. The application layer depends on the domain and infrastructure
layers, and the interface layer depends only on the application layer.

The library default functionality is designed to be extended or replaced easily.


Onion architecture
==================

An interface layer will depend on the application layer.

The library's application layer depends on the domain model and infrastructure
layers. An application object has a repository, from which existing aggregates
can be retrieved. It may also have policies, such as a persistence policy which
stores domain events in an event store. The application's repository shares the
event store with the persistence policy, and uses the event store to retrieve
events when reconstructing the state of an aggregate.

The library's domain layer contains domain model events and aggregates. Aggregates
define a set of domain event classes, and have command methods to trigger new domain
events. Nothing in the domain layer depends on anything in the infrastructure layer.
These stand-alone library classes are implemented with "double underscore" methods,
to keep the normal object namespace free to be used for domain modelling.

The library's infrastructure layer encapsulates infrastructural services
required by event sourced applications, in particular by the event
store. This layer is the original core of this library (the other
layers were originally included merely as reference examples, to
demonstrate how to use the infrastructure).


Domain event store
==================

The central object of the infrastructure layer is the event store. The event
store object uses a sequenced item mapper and a record manager. Domain events are
serialised to (and deserialised from) sequenced items by the sequenced item mapper.
The record manager records (and reads) sequenced items in a particular database system.
