=============
Release notes
=============

It is the aim of the project that releases with the same major version
number are backwards compatible, within the scope of the documented
examples. New major versions indicate a backward incompatible changes
have been introduced since the previous major version. New minor
version indicate new functionality has been added, or existing functionality
extended. New point version indicates existing code or documentation
has been improved in a way that neither breaks backwards compatibility
nor extends the functionality of the library.


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
