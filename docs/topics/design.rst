======
Design
======

The design of the library follows the layered architecture of domain
driven design: interfaces, application, domain, and infrastructure.

The library is designed to allow its default functionality to be extended or replaced easily.


Layered architecture
====================

The library's infrastructure layer encapsulates infrastructural services
required by event sourced applications, in particular by the event
store. This layer is the original core of this library (the other
layers were provided originally as reference examples, to demonstrate
how to use the infrastructure).

The central object of the infrastructure layer is the event store. The event
store object uses a sequenced item mapper and a record manager. Domain events are
serialised to (and deserialised from) sequenced items by the sequenced item mapper.
The record manager records (and reads) sequenced items in a particular database system.

The library's domain layer contains domain model events and aggregates. Aggregates
define a set of domain event classes, and have command methods to trigger new domain
events. Nothing in the domain layer depends on anything in the infrastructure layer.
These stand-alone library classes are implemented with "double underscore" methods, to
keep the normal object namespace free to be used for domain modelling.

The library's application layer depends on the domain model and infrastructure
layers. An application object has a repository, from which existing aggregates
can be retrieved. It may also have policies, such as a persistence policy which stores domain
events in an event store. The application's repository shares the event store with the persistence
policy, and uses the event store to retrieve events when reconstructing the state of an aggregate.

Any interface layer will depend on the application layer.
