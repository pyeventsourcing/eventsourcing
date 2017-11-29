Release notes
=============

It is the aim of the project that releases with the same major version
number are backwards compatible, within the scope of the documented
examples. New major versions indicate a backward incompatible changes
have been introduced since the previous major version.

Version 4.x series will introduce typed sequences (previously sequences
were untyped which isn't ideal for aggregate repositories).

Version 3.x series was a released after quite of a lot of refactoring.

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
