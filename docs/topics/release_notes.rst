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


Version 9.x
===========

Version 9.x series is a rewrite of the library that distills most of
the best parts of the previous versions of the library into faster
and simpler code. This version is recommended for new projects.
It is not backwards-compatible with previous major versions. However
the underlying principles are the same, and so conversion of
code and stored events is very possible.


Version 9.1.4 (released 20 October 2021)
----------------------------------------

Fixed discrepancy between Application save() and Follower record()
methods, so that Follower applications will do automatic snapshotting
based on their 'snapshotting_intervals' after their policy() has been
called, as expected.


Version 9.1.3 (released 8 October 2021)
---------------------------------------

Added "trove classifier" for Python 3.10.


Version 9.1.2 (released 1 October 2021)
---------------------------------------

Clarified Postgres configuration options (POSTGRES_LOCK_TIMEOUT and
POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT) require integer seconds.
Added py.typed file (was missing since v9).


Version 9.1.1 (released 20 August 2021)
---------------------------------------

Changed PostgreSQL schema to use BIGSERIAL (was SERIAL) for notification IDs.


Version 9.1.0 (released 18 August 2021)
---------------------------------------

Added support for setting environment when constructing application.
Added "eq" and "repr" methods on aggregate base class.
Reinstated explicit definition of Aggregate.Created class.
Added Invoice example, and Parking Lot example.
Fixed bug when decorating property setter (use method argument name).
Improved type annotations.
Adjusted order of calling domain event mutate() and apply() methods,
so apply() method is called first, in case exceptions are raised by
apply() method so that the aggregate object can emerge unscathed
whereas previously its version number and modified time would always
be changed. Improved robustness of recorder classes, with more attention
to connection state, closing connections on certain errors, retrying
operations under certain conditions, and especially by changing the
postgres recorders to obtain 'EXCLUSIVE' mode table lock when inserting
events. Obtaining the table lock in PostgreSQL avoids interleaving of
inserts between commits, which avoids event notifications from being
committed with lower notification IDs than event notifications that
have already been committed, and thereby prevents readers who are
tailing the notification log of an application from missing event
notifications for this reason. Added various environment variable
options: for sqlite a lock timeout option; and for postgres a max
connection age option which allows connections over a certain age
to be closed when idle, a connection pre-ping option, a lock timeout
option, and an option to timeout sessions idle in transaction so
that locks can be released even if the database client has somehow
ceased to continue its interactions with the server in a way that
leave the session open. Improved the exception classes, to follow
the standard Python DBAPI class names, and to encapsulate errors
from drivers with library errors following this standard. Added
methods to notification log and reader classes to allow notifications
to be selected directly. Changed Follower class to select()
rather than read() notifications. Supported defining initial version
number of aggregates on aggregate class (with INITIAL_VERSION attribute).


Version 9.0.3 (released 17 May 2021)
--------------------------------------

Changed PostgreSQL queries to use transaction class context manager
(transactions were started and not closed). Added possibility to
specify a port for Postgres (thanks to Valentin Dion). Added \*\*kwargs
to Application.save() method signature, so other things can be
passed down the stack. Fixed reference in installing.rst (thanks to
Karl Heinrichmeyer). Made properties out of aggregate attributes:
'modified_on' and 'version'. Improved documentation.


Version 9.0.2 (released 16 April 2021)
--------------------------------------

Fixed issue with type hints in PyCharm v2021.1 for methods decorated with the @event decorator.


Version 9.0.1 (released 29 March 2021)
--------------------------------------

Improved documentation. Moved cipher base class to avoid importing cipher module.


Version 9.0.0 (released 13 March 2021)
--------------------------------------

First release of the distilled version of the library. Compared with
previous versions, the code and documentation are much simpler. This
version focuses directly on expressing the important concerns, without
the variations and alternatives that had been accumulated over the past
few years of learning and pathfinding.

The highlight is the new :ref:`declarative syntax <Declarative syntax>`
for event sourced domain models.

Dedicated persistence modules for SQLite and PostgresSQL have been
introduced. Support for SQLAlchemy and Django, and other databases,
has been removed. The plan is to support these in separate package
distributions. The default "plain old Python object" infrastructure
continues to exist, and now offers event storage and retrieval
performance of around 20x the speed of using PostgreSQL and around
4x the speed of using SQLite in memory.

The event storage format is more efficient, because originator IDs and
originator versions are removed from the stored event state before
serialisation, and then reinstated on serialisation.

Rather than the using "INSERT SELECT MAX" SQL statements, database
sequences are used to generate event notifications. This avoids table
conflicts that sometimes caused exceptions and required retries when
storing events. Although this leads to notification ID sequences that
may have gaps, the use of sequences means there is still no risk of
event notifications being inserted in the gaps after later event
notifications have been processed, which was the motivation for using
gapless sequences in previous versions. The notification log and log
reader classes have been adjusted to support the possible existence of
gaps in the notification log sequence.

The transcoder is more easily extensible, with the new style for defining
and registering individual transcoding objects to support individual types
of object that are not supported by default.

Domain event classes have been greatly simplified, with the deep hierarchy
of entity and event classes removed in favour of the simple aggregate base
class.

The repository class has been changed to provide a single get() method. It no
longer supports the Python "indexing" square-bracket syntax, so that there is
just one way to get an aggregate regardless of whether the requested version
is specified or not.

Application configuration of persistence infrastructure is now driven by
environment variables rather than constructor parameters, leading to a
simpler interface for application object classes. The mechanism for storing
aggregates has been simplified, so that aggregates are saved using the
application "save" method. A new "notify" method has been added to the
application class, to support applications that need to know when new
events have just been recorded.

The mechanism by which aggregates published their events and a
"persistence subscriber" subscribed and persisted published domain events
has been completely removed, since aggregates that are saved always need
some persistence infrastructure to store the events, and it is the
responsibility of the application to bring together the domain model and
infrastructure, so that when an aggregate can be saved there is always
an application.

Process application policy methods are now given a process event object
and will use it to collect domain events, using its "save" method, which
has the same method signature as the application "save" method. This
allows policies to accumulate new events on the process event object
in the order they were generated, whereas previously if new events
were generated on one aggregate and then a second and then the first,
the events of one aggregate would be stored first and the events of
the second aggregate would be stored afterwards, leading to an incorrect
ordering of the domain events in the notification log. The process
event object existed in previous versions, was used to keep track
of the position in a notification log of the event notification
that was being processed by a policy, and continues to be used
for that purpose.

The system runners have been reduced to the single-threaded and
multi-threaded runners, with support for running with Ray and gRPC
and so on removed (the plan being to support these in separate package
distributions).

Altogether, these changes mean the core library now depends only on
the PythonStandard Library, except for the optional extra dependencies
on a cryptographic library (PyCryptodome) and a PostgresSQL driver (psycopg2),
and the dependencies of development tools. Altogether, these changes make the
test suite much faster to run (several seconds rather than several minutes for
the previous version). These changes make the build time on CI services much
quicker (around one minute, rather than nearly ten minutes for the previous
version). And these changes make the library more approachable and fun for
users and library developers. Test coverage has been increased to 100% line
and branch coverage. Also mypy and flake8 checking is done.

The documentation has been rewritten to focus more on usage of the library code,
and less on explaining surrounding concepts and considerations.


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
be used as an event store by event-sourced applications.

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
