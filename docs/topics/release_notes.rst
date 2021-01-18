=============
Release notes
=============

It is the aim of the project that releases with the same major version
number are backwards compatible, within the scope of the documented
examples. New major versions indicate backwards incompatible changes
have been introduced since the previous major version. New minor
version indicate new functionality has been added, or existing functionality
extended. New point version indicates existing code or documentation
has been improved in a way that neither breaks backwards compatibility
nor extends the functionality of the library.


Version 8.x
===========

Version 8.x series brings more efficient storage, static type hinting,
improved transcoding, event and entity versioning, and integration with
Axon Server (specialist event store) and Ray. Code for defining and running
systems of application, previously in the "application" package, has been
moved to a new "system" package.


Version 8.3.0 (released 9 January 2021)
---------------------------------------

Added gRPC runner. Improved Django record manager, so that it supports
setting notification log IDs in the application like the SQLAlchemy
record manager (this optionally avoids use of the "insert select max"
statement and thereby makes it possible to exclude domain events from
the notification log at the risk of non-gapless notification log
sequences). Also improved documentation.


Version 8.2.5 (released 22 Dec 2020)
--------------------------------------

Increased versions of dependencies on requests, Django, Celery, PyMySQL.

Version 8.2.4 (released 12 Nov 2020)
--------------------------------------

Fixed issue with using Oracle database, where a trailing semicolon
in an SQL statement caused the "invalid character" error (ORA-00911).

Version 8.2.3 (released 19 May 2020)
--------------------------------------

Improved interactions with process applications in RayRunner
so that they have the same style as interactions with process
applications in other runners. This makes the RayRunner more
interchangeable with the other runners, so that system client
code can be written to work with any runner.


Version 8.2.2 (released 16 May 2020)
--------------------------------------

Improved documentation. Updated dockerization for local
development. Added Makefile, to setup development environment,
to build and run docker containers, to run the test suite, to
format the code, and to build the docs. Reformatted the code.


Version 8.2.1 (released 11 March 2020)
--------------------------------------

Improved documentation.


Version 8.2.0 (released 10 March 2020)
--------------------------------------

Added optional versioning of domain events and entities, so that
domain events and entity snapshots can be versioned and old
versions of state can be upcast to new versions.

Added optional correlation and causation IDs for domain events,
so that a story can be traced through a system of applications.

Added AxonApplication and AxonRecordManager so that Axon Server can
be used as an event store by event sourced applications.

Added RayRunner, which allows a system of applications to be run with
the Ray framework.


Version 8.1.0 (released 11 January 2020)
----------------------------------------

Improved documentation. Improved transcoding (e.g. tuples
are encoded as tuples also within other collections). Added
event hash method name to event attributes, so that event hashes
created with old version of event hashing can still be checked.
Simplified repository base classes (removed "event player" class).


Version 8.0.0 (released 7 December 2019)
----------------------------------------

The storage of event state has been changed from strings to bytes. This
is definitely a backwards incompatible change. Previously state bytes were
encoded with base64 before being saved as strings, which adds 33% to the size
of each stored state. Compression of event state is now an option, independently
of encryption, and compression is now configurable (defaults to zlib module,
other compressors can be used). Attention will need to be paid to one of two
alternatives. One alternative is to migrate your stored events (the state field),
either from being stored as plaintext strings to being stored as plaintext bytes
(you need to encode as utf-8), or from being stored as ciphertext bytes encoded
with base64 decoded as utf-8 to being stored as ciphertext bytes (you need to
encode as utf-8 and decode base64). The other alternative is to carry on using
the same database schema, define custom stored event record classes in your project
(copied from the previous version of the library), and extend the record manager
to convert the bytes to strings and back. A later version of this library may
bring support for one or both of these options, so if this change presents a
challenge, please hold off from upgrading, and discuss your situation with the
project developer(s). There is nothing wrong with the previous version, and you
can continue to use it.

Other backwards incompatible changes involve renaming a number of methods, and
moving classes and also modules (for example, the system modules have been moved
from the applications package to a separate package). Please see the commit log
for all the details.

This version also brings improved and expanded transcoding, additional type
annotations, automatic subclassing on domain entities of domain events (not
enabled by default), an option to apply the policy of a process application
to all events that are generated by its policy when an event notification
is processed (continues until all successively generated events have been
processed, with all generated events stored in the same atomic process event,
as if all generated events were generated in a single policy function).

Please note, the transcoding now supports the encoding of tuples, and named tuples,
as tuples. Previously tuples were encoded by the JSON transcoding as
lists, and so tuples became lists, which is the default behaviour on the core
json package. So if you have code that depends on the transcoder converting
tuples to lists, then attention will have to paid to the fact that tuples will
now be encoded and returned as tuples. However, any existing stored events generated
with an earlier version of this library will continue to be returned as lists,
since they were encoded as lists not tuples.

Please note, the system runner class was changed to keep references to
constructed process application classes in the runner object, rather than the
system object. If you have code that accesses the process applications
as attributes on the system object, then attention will need to be paid to
accessing the process applications by class on the runner object.


Version 7.x
===========

Version 7.x series refined the "process and system" code.


Version 7.2.4 (released 9 Oct 2019)
------------------------------------

Version 7.2.4 fixed an issue in running the test suite.


Version 7.2.3 (released 9 Oct 2019)
------------------------------------

Version 7.2.3 fixed a bug in MultiThreadedRunner.


Version 7.2.2 (released 6 Oct 2019)
------------------------------------

Version 7.2.2 has improved documentation for "reliable projections".


Version 7.2.1 (released 6 Oct 2019)
------------------------------------

Version 7.2.1 has improved support for "reliable projections",
which allows custom records to be deleted (previously only
create and update was supported). The documentation for
"reliable projections" was improved. The previous code
snippet, which was merely suggestive, was replaced by a
working example.


Version 7.2.0 (released 1 Oct 2019)
------------------------------------

Version 7.2.0 has support for "reliable projections" into custom
ORM objects that can be coded as process application policies.

Also a few issues were resolved: avoiding importing Django models from library
when custom models are being used to store events prevents model conflicts;
fixed multiprocess runner to work when an application is not being followed
by another; process applications now reflect off the sequenced item tuple when
reading notifications so that custom field names are used.


Version 7.1.6 (released 2 Aug 2019)
------------------------------------

Version 7.1.6 fixed an issue with the notification log reader. The notification
log reader was sometimes using a "fast path" to get all the notifications without
paging through the notification log using the linked sections. However, when there
were too many notification, this failed to work. A few adjustments were made
to fix the performance and robustness and configurability of the notification
log reading functionality.


Version 7.1.5 (released 26 Jul 2019)
------------------------------------

Version 7.1.5 improved the library documentation with better links to
module reference pages. The versions of dependencies were also updated,
so that all versions of dependencies are the current stable versions
of the package distributions on PyPI. In particular, requests was
updated to a version that fixes a security vulnerability.


Version 7.1.4 (released 10 Jul 2019)
------------------------------------

Version 7.1.4 improved the library documentation.


Version 7.1.3 (released 4 Jul 2019)
------------------------------------

Version 7.1.3 improved the domain model layer documentation.


Version 7.1.2 (released 26 Jun 2019)
------------------------------------

Version 7.1.2 fixed method 'construct_app()' on class 'System' to set 'setup_table'
on its process applications using the system's value of 'setup_tables'. Also
updated version of dependency of SQLAlchemy-Utils.


Version 7.1.1 (released 21 Jun 2019)
------------------------------------

Version 7.1.1 added 'Support options' and 'Contributing' sections to the documentation.


Version 7.1.0 (released 11 Jun 2019)
------------------------------------

Version 7.1.0 improved structure to the documentation.


Version 7.0.0 (released 21 Feb 2019)
------------------------------------

Version 7.0.0 brought many incremental improvements across the library,
especially the ability to define an entire system of process applications
independently of infrastructure. Please note, records fields have been renamed.


Version 6.x
===========

Version 6.x series was the first release of the "process and system" code.


Version 6.2.0 (released 15 Jul 2018)
------------------------------------

Version 6.2.0 (released 26 Jun 2018)
------------------------------------

Version 6.1.0 (released 14 Jun 2018)
------------------------------------

Version 6.0.0 (released 23 Apr 2018)
------------------------------------

Version 5.x
===========

Version 5.x added support for Django ORM. It was released
as a new major version after quite a lot of refactoring made
things backward-incompatible.

Version 5.1.1 (released 4 Apr 2018)
------------------------------------

Version 5.1.0 (released 16 Feb 2018)
------------------------------------

Version 5.0.0 (released 24 Jan 2018)
------------------------------------

Support for Django ORM was added in version 5.0.0.

Version 4.x
===========

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

Version 4.0.0 (released 11 Dec 2017)
------------------------------------


Version 3.x
===========

Version 3.x series was a released after quite of a lot of refactoring
made things backwards-incompatible. Documentation was greatly improved, in
particular with pages reflecting the architectural layers of the library
(infrastructure, domain, application).

Version 3.1.0 (released 23 Nov 2017)
------------------------------------

Version 3.0.0 (released 25 May 2017)
------------------------------------

Version 2.x
===========

Version 2.x series was a major rewrite that implemented two distinct
kinds of sequences: events sequenced by integer version numbers and
events sequenced in time, with an archetypal "sequenced item" persistence
model for storing events.

Version 2.1.1 (released 30 Mar 2017)
------------------------------------

Version 2.1.0 (released 27 Mar 2017)
------------------------------------

Version 2.0.0 (released 27 Mar 2017)
------------------------------------



Version 1.x
===========

Version 1.x series was an extension of the version 0.x series,
and attempted to bridge between sequencing events with both timestamps
and version numbers.

Version 1.2.1 (released 23 Oct 2016)
------------------------------------

Version 1.2.0 (released 23 Oct 2016)
------------------------------------

Version 1.1.0 (released 19 Oct 2016)
------------------------------------

Version 1.0.10 (released 5 Oct 2016)
------------------------------------

Version 1.0.9 (released 17 Aug 2016)
------------------------------------

Version 1.0.8 (released 30 Jul 2016)
------------------------------------

Version 1.0.7 (released 13 Jul 2016)
------------------------------------

Version 1.0.6 (released 7 Jul 2016)
------------------------------------

Version 1.0.5 (released 1 Jul 2016)
------------------------------------

Version 1.0.4 (released 30 Jun 2016)
------------------------------------

Version 1.0.3 (released 30 Jun 2016)
------------------------------------

Version 1.0.2 (released 8 Jun 2016)
------------------------------------

Version 1.0.1 (released 7 Jun 2016)
------------------------------------



Version 0.x
===========

Version 0.x series was the initial cut of the code, all events were
sequenced by timestamps, or TimeUUIDs in Cassandra, because the project
originally emerged whilst working with Cassandra.

Version 0.9.4 (released 11 Feb 2016)
------------------------------------

Version 0.9.3 (released 1 Dec 2015)
------------------------------------

Version 0.9.2 (released 1 Dec 2015)
------------------------------------

Version 0.9.1 (released 10 Nov 2015)
------------------------------------

Version 0.9.0 (released 14 Sep 2015)
------------------------------------

Version 0.8.4 (released 14 Sep 2015)
------------------------------------

Version 0.8.3 (released 5 Sep 2015)
------------------------------------

Version 0.8.2 (released 5 Sep 2015)
------------------------------------

Version 0.8.1 (released 4 Sep 2015)
------------------------------------

Version 0.8.0 (released 29 Aug 2015)
------------------------------------

Version 0.7.0 (released 29 Aug 2015)
------------------------------------

Version 0.6.0 (released 28 Aug 2015)
------------------------------------

Version 0.5.0 (released 28 Aug 2015)
------------------------------------

Version 0.4.0 (released 28 Aug 2015)
------------------------------------

Version 0.3.0 (released 28 Aug 2015)
------------------------------------

Version 0.2.0 (released 27 Aug 2015)
------------------------------------

Version 0.1.0 (released 27 Aug 2015)
------------------------------------

Version 0.0.1 (released 27 Aug 2015)
------------------------------------
