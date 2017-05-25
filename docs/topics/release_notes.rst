Release notes
=============

It is the aim of the project that releases with the same major version
number are backwards compatible.

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
