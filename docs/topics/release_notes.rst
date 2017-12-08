Release notes
=============

It is the aim of the project that releases with the same major version
number are backwards compatible, within the scope of the documented
examples. New major versions indicate a backward incompatible changes
have been introduced since the previous major version.

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
AES-GCM to allow authentication of encrypted data returned by database.
Documentation was improved, in particular with pages for each of the
layers in the library (infrastructure, domain model, application).

Version 3.x series was a released after quite of a lot of refactoring
made things backwards-incompatible.

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
