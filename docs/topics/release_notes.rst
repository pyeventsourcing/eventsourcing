Release notes
=============

It is the aim of the project that releases with the same major version
number are backwards compatible, within the scope of the documented
examples. New major versions indicate a backward incompatible changes
have been introduced since the previous major version.

If you need help upgrading code and migrating data, please get in touch.

Version 7.1.0 brings improved documentation.

Version 7.x series brings many incremental improvements across the library,
especially the ability to define an entire system of process applications
independently of infrastructure. Please note, records fields have been renamed.

Version 6.x series was the first release of the "process and system" code.

Version 5.x series was released after quite a lot of refactoring made
things backward-incompatible.

Version 4.x series was released after quite a lot of refactoring made
things backward-incompatible. Object namespaces for entity and event
classes was cleaned up, by moving library names to double-underscore
prefixed and postfixed names. Domain events can be hashed, and also
hash-chained together, allowing entity state to be verified.
Created events were changed to have originator_topic, which allowed
other things such as mutators and repositories to be greatly
simplified. Mutators are now by default expected to be implemented
on entity event classes. Event timestamps were changed from floats
to decimal objects, an exact number type. Cipher was changed to use
AES-GCM to allow verification of encrypted data retrieved from a
database.

Also, the record classes for SQLAlchemy were changed to have an
auto-incrementing ID, to make it easy to follow the events of an
application, for example when updating view models, without additional
complication of a separate application log. This change makes the
SQLAlchemy library classes ultimately less "scalable" than the Cassandra
classes, because an auto-incrementing ID must operate from a single thread.
Overall, it seems like a good trade-off for early-stage development. Later,
when the auto-incrementing ID bottleneck would otherwise throttle
performance, "scaling-up" could involve switching application
infrastructure to use a separate application log.

Also, support for Django ORM was added in version 4.1.0.

Version 3.x series was a released after quite of a lot of refactoring
made things backwards-incompatible. Documentation was greatly improved, in
particular with pages reflecting the architectural layers of the library
(infrastructure, domain, application).

Version 2.x series was a major rewrite that implemented two distinct
kinds of sequences: events sequenced by integer version numbers and
events sequenced in time, with an archetypal "sequenced item" persistence
model for storing events.

Version 1.x series was an extension of the version 0.x series,
and attempted to bridge between sequencing events with both timestamps
and version numbers.

Version 0.x series was the initial cut of the code, all events were
sequenced by timestamps, or TimeUUIDs in Cassandra, because the project
originally emerged whilst working with Cassandra.
