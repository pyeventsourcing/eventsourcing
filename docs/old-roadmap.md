## Roadmap

This is just a list of potentially useful enhancements, refinements, or extensions.

* Stored event repository to persist stored events using MongoDB (forthcoming)

* Stored event repository to persist stored events using HBase (forthcoming)

* Stored event repository to persist stored events using DynamoDB (forthcoming)

* Subscriber that publishes domain events to messaging infrastructure and
  subscriber that republishes events in another application (forthcoming)
  * RabbitMQ
  * Amazon SQS
  * ZeroMQ

* Event sourced indexes, as persisted event source projections, to discover extant entity IDs (forthcoming)

* Something to store serialized event attribute values separately from the other event information, to prevent large
attribute values inhibiting performance and stability - different sizes could be stored in different ways...
(forthcoming)

* Optionally decouple topics from actual code, so classes can be moved

* Base class for event sourced projections or views (forthcoming)

    * In memory event sourced projection, which needs to replay entire event stream when system starts up (forthcoming)

    * Persistent event sourced projection, which stored its projected state, but needs to replay entire event stream
      when initialized  (forthcoming)

* Event pointer, object that refer to an event in a stream (forthcoming)

* Updating stored events, to support domain model migration (forthcoming)

* Different kinds of stored event
    * IDs generated from content, e.g. like Git (forthcoming)
    * cryptographically signed stored events (forthcoming)

* Branch and merge mechanism for domain events (forthcoming)

* Support for asynchronous I/O, with an application that uses an event loop (forthcoming)

* Boxes (forthcoming, experimental) The notification log pattern enables a flow of events between applications
in different bounded contexts, and suggests an effective way of avoiding a monolithic
application by developing a suite of smaller, collaborating, event driven
and event sourced applications that can maintain integrity despite premature
application termination and occasional network partitioning. "Box" is this project's working
name for the archetypal event sourced application that is dedicated to a bounded context,
whilst also being capable of collaborating (using notifications) with other such application
in other bounded contexts. The well factored monolith amounts to having all boxes running in
one container, with notifications being made synchronously in process. Microservices arise
simply from moving a box to a new container, with notifications then propagated across the
process boundaries. As Eric Evans has suggested, harder social boundaries are perhaps a necessary
condition to ensure a domain driven design can be a socially successful design, due to the rough
and tumble of day-to-day software development, and the fact that software developers double in
number every five years, so that on average half the programmers have less than five years
experience, which might not be enough adequately to practise design approaches such as DDD.
