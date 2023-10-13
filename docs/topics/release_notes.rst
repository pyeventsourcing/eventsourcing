=============
Release notes
=============

It is the aim of the project that releases with the same major version
number are backwards compatible, within the scope of the documented
examples. New major versions indicate backward incompatible changes
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


Version 9.2.21 (released 13 Oct 2023)
-------------------------------------

* Changed Follower.follow() to pass application's mapper class into factory.mapper()
  so that if an application uses a custom mapper class for its own recorders then
  it will use that type also for mapping event notifications from upstream applications
  in a system.

Version 9.2.20 (released 19 May 2023)
---------------------------------------

* Fixed invite link to Slack workspace in docs.

Version 9.2.19 (released 19 April 2023)
---------------------------------------

* Fixed invite link to Slack workspace in docs (had somehow become invalid).
* Fixed new mypy issue with call to TDomainEvent.create_timestamp() in
  EventSourcedLog class, by directly calling create_utc_timestamp().
* Slightly adjusted typing annotations in Aggregate class.


Version 9.2.18 (released 22 March 2023)
---------------------------------------

* Allowing access to event timestamp value in aggregate command method,
  and event timestamp to be set by caller, by including 'timestamp' as
  a parameter of the method signature.
* Added support for calling "unbound" decorated aggregate command methods.
* Improved documentation (doc strings, and discussion of aggregate events).

Version 9.2.17 (released 10 January 2023)
-----------------------------------------

* Improved documentation (Tutorial and Module pages).
* Fixed POPOApplicationRecorder.selection_notifications() to avoid using negative
  indexes into its list of stored events.


Version 9.2.16 (released 11 June 2022)
--------------------------------------

* Improved documentation (Tutorial pages).


Version 9.2.15 (released 6 June 2022)
-------------------------------------

* Improved documentation (Installation, Support, Introduction, and Tutorial pages).


Version 9.2.14 (released 24 May 2022)
-------------------------------------

* Fixed test case for non-interleaving notification IDs
  (eventsourcing_eventstoredb extension needs non-empty
  topic strings).


Version 9.2.13 (released 14 May 2022)
-------------------------------------

* Fixed tutorial part 2 (had broken 'mutate' method definition).


Version 9.2.12 (released 9 May 2022)
------------------------------------

* Fixed typing of EventSourcedLog class, and deprecated LogEvent class.
* Improved documentation:

  * improved wording in section "Event-sourced log";
  * fixed broken link in docs (to PostgreSQL's full text search doc);
  * added links to extension packages;
  * fixed docstrings in ProcessRecorder; and
  * fixed wording in section "Aggregates in DDD".

* Adjusted application and persistence test cases (to accommodate testing
  extensions for Axon Server and EventStoreDB).

Version 9.2.11 (released 4 May 2022)
------------------------------------

* Improved the documentation (better wording and examples).
* Improved test cases (to accommodate eventsourcing-axonserver).


Version 9.2.10 (released 27 April 2022)
---------------------------------------

* Improved the documentation (better wording in module docs,
  added new application example).


Version 9.2.9 (released 23 April 2022)
--------------------------------------

* Improved the documentation (improved examples).
* Fixed event decorator to have __doc__, __annotations__, and __module__ from original method.


Version 9.2.8 (released 21 April 2022)
--------------------------------------

* Improved the documentation (missing doc strings).
* Fixed detection of the topic of a system.


Version 9.2.7 (released 21 April 2022)
--------------------------------------

* Improved the documentation (introduction, installation, example content management application).


Version 9.2.6 (released 20 April 2022)
--------------------------------------

* Improved typing annotations.


Version 9.2.5 (released 16 April 2022)
--------------------------------------

* Reverted create_timestamp() to use datetime.now().
* Improved aggregate examples.


Version 9.2.4 (released 7 April 2022)
-------------------------------------

* Added examples showing how persistence and application modules can be
  used with alternative infrastructure, including Pydantic event classes
  and immutable aggregate classes.
* Added protocol types for events and aggregates so that alternative
  domain model classes can be both used and type checked with mypy.
* Added application environment option 'DEEPCOPY_FROM_AGGREGATE_CACHE'
  to allow deepcopy to be always avoided when using immutable aggregates
  (enabled by default).
* Added repository get() method argument 'deepcopy_from_cache' to allow
  to deepcopy to be avoided when using aggregates in read-only queries.
* Added application environment option 'AGGREGATE_CACHE_FASTFORWARD_SKIPPING'
  to skip waiting for aggregate-specific lock for serialised database query
  to get any new events to fast-forward a cached aggregate when another
  thread is already doing this, hence avoiding delaying response and spikes
  on database load at the expense of risking seeing the very latest version
  of an aggregate that has just been updated (not enabled by default).
* Changed application to avoid putting aggregates in the cache after they
  have been saved, unless fast-forwarding of cached aggregates is disabled.
  This avoids the risk that the cache might corrupted by a mistaken mutation
  in a command, and means the cache state will be constructed purely from
  recorded events (just like snapshots are).
* Changed create_timestamp() to use time.monotonic().
* Improved docs (docstring in runner, double word in tutorial, and better
  wording in domain module doc, overview in tutorial).
* Fixed a call to '_reconstruct_aggregate' to use given 'projector_func'
  arg (was using default 'mutator_func').
* Adjusted order of looking for 'PERSISTENCE_MODULE', 'INFRASTRUCTURE_FACTORY'
  and 'FACTORY_TOPIC' in environment (so that legacy alternatives are looked
  for last, allowing the persistence module to be set to POPO when constructing
  application objects for their transcoder in remote clients so that the
  application doesn't try to connect to a real database).


Version 9.2.3 (released 3 March 2022)
-------------------------------------

* Fixed single- and multi-threaded runners to be more robust when
  multiple instances of the same system are running.
* Fixed EventSourcedLog class to be more extensible.
* Fixed ordering of edges in a System to follow order of definition.
* Fixed various errors in the documentation.
* Adjusted JSONTranscoder to use JSONEncoder with ensure_ascii=False.


Version 9.2.2 (released 17 February 2022)
-----------------------------------------

* Added documentation for the __contains__() method of Repository class
  to indicate the possibility to use the Python 'in' keyword to check
  whether or not an aggregate exists in the repository.
* Added per-aggregate locking around fast-forwarding of cached aggregates,
  because fast-forwarding isn't thread-safe.
* Mentioned in the documentation the cookie project template for starting
  new projects.
* Fixed other minor issues in the documentation (Repository get() method,
  discussion of version numbers and expressing dependency of a project
  on the library, etc).


Version 9.2.1 (released 15 February 2022)
-----------------------------------------

* Improved decode performance of JSONTranscoder class.
* Improved encode behaviour of JSONTranscoder class (no whitespace in separators).
* Improved documentation about compression and encryption.
* Fixed documentation (typos, and developer install instructions).
* Adjusted tests, so transcoder test is available for extensions.

Version 9.2.0 (released 1 February 2022)
----------------------------------------

* Removed generic typing of 'Application' with the stored aggregate type.
  An application repository can store more than one type of aggregate so this
  typing (inheritance) could be confusing.
* Added support for specifying the persistence module to be used by an application
  (see environment variable 'PERSISTENCE_MODULE') rather than specifying the topic
  of a factory class as the way to select a persistence module.
* Added support for specifying all application environment variables with environment
  variable names that are prefixed with the application name, so that different
  applications can use a distinct set of environment variables (previously this
  was supported only for some environment variables).
* Added support for setting the name of an application, that is different from the
  class name. This allows application classes to be renamed, and also supports
  having more than one application class in the same environment and persistence
  namespace, or "bounded context" (use the 'name' attribute of application classes).
* Added ProcessEvent.collect_events() method and deprecated save(),
  effectively renaming this method for clarity of its purpose.
* Added ProcessingEvent to replace (and deprecate) ProcessEvent. The new name
  avoids confusion with the object not being an "action" but rather used to
  propagate processing of an aggregate event down to application subscribers.
* Added Application.notification_log and deprecated Application.log, effectively
  renaming this attribute to avoid confusion with event-sourced logs.
* Added connection pooling for the postgres and sqlite persistence modules
  (see 'ConnectionPool').
* Added support for caching of aggregates in aggregate repository
  (see 'AGGREGATE_CACHE_MAXSIZE' and 'AGGREGATE_CACHE_FASTFORWARD').
* Added support for event-sourced logging, e.g. of aggregate IDs of a
  particular type as one way of supporting discovery of aggregate IDs
  (see 'EventSourcedLog').
* Added support for returning new notification IDs after inserting events
  in application recorders (see all methods involved with storing events).
* Added support for selecting event notifications that match a list of
  topics – previously it wasn't possible to filter event notifications by
  topic (see 'follow_topics').
* Added support for mentioning 'id' in aggregate init method when using
  explicitly defined event classes (previously this only worked with
  implicitly defined event classes).
* Added support for specifying in which PostgreSQL schema tables
  should be created (see 'POSTGRES_SCHEMA').
* Fixed postgres module to alias statement names that are too long, and to
  assert table names are not greater than the maximum permissible length.
* Excluded test cases and example packages from being included in releases
  (whilst still including base test cases and test utilities used by extensions).
* Improved documentation (in numerous ways). For example, the central example in
  docs was changed from `World` to `Dog` most importantly to avoid the
  aggregate attribute 'history' which was overloaded in this context.
* Improved SingleThreadedRunner and MultiThreadedRunner to push domain
  events to followers, and to fall back to pulling when gaps are detected
  – this avoids wasteful deserialization of stored events.
* Improved MultiThreadedRunner to pull concurrently when
  an application is following more than one other application.
* Improved Follower's process_event() method to detect when a tracking record
  conflict occurs (meaning event processing was somehow being repeated) hence
  avoiding and propagating an IntegrityError and thereby allowing processing
  to continue to completion without this resulting in an error (in both
  SingleThreadedRunner and MultiThreadedRunner).


Version 9.1.9 (released 5 December 2021)
-----------------------------------------

* Fixed register_topic() for race condition when setting topic cache with identical value.


Version 9.1.8 (released 30 November 2021)
-----------------------------------------

* Fixed postgres.py to recreate connection and retry after OperationalError.


Version 9.1.7 (released 19 November 2021)
-----------------------------------------

* Fixed errors in the documentation.


Version 9.1.6 (released 18 November 2021)
-----------------------------------------

* Fixed typos and wording in the documentation.


Version 9.1.5 (released 17 November 2021)
-----------------------------------------

* Improved the documentation, examples, and tests.
* Fixed PostgreSQL recorder to use bigint for notification_id
  in tracking table, and to lock table only when inserting
  stored events into a total order (ie not when inserting
  snapshots).
* Refactored several things:

  * extracted register_topic() function;
  * changed handling of event attributes to pass
    in what is expected by a decorated method;
  * extracted aggregate mutator function allowing non-default mutator
    function to be used with repository get() method;
  * stopped using deprecated Thread.setDaemon() method.

* Improved static type hinting.

Version 9.1.4 (released 20 October 2021)
----------------------------------------

* Fixed discrepancy between Application save() and Follower record()
  methods, so that Follower applications will do automatic snapshotting
  based on their 'snapshotting_intervals' after their policy() has been
  called, as expected.


Version 9.1.3 (released 8 October 2021)
---------------------------------------

* Added "trove classifier" for Python 3.10.


Version 9.1.2 (released 1 October 2021)
---------------------------------------

* Clarified Postgres configuration options (POSTGRES_LOCK_TIMEOUT and
  POSTGRES_IDLE_IN_TRANSACTION_SESSION_TIMEOUT) require integer seconds.
* Added py.typed file (was missing since v9).


Version 9.1.1 (released 20 August 2021)
---------------------------------------

* Changed PostgreSQL schema to use BIGSERIAL (was SERIAL) for notification IDs.


Version 9.1.0 (released 18 August 2021)
---------------------------------------

* Added support for setting environment when constructing application.
* Added "eq" and "repr" methods on aggregate base class.
* Reinstated explicit definition of Aggregate.Created class.
* Added Invoice example, and Parking Lot example.
* Fixed bug when decorating property setter (use method argument name).
* Improved type annotations.
* Adjusted order of calling domain event mutate() and apply() methods,
  so apply() method is called first, in case exceptions are raised by
  apply() method so that the aggregate object can emerge unscathed
  whereas previously its version number and modified time would always
  be changed.
* Improved robustness of recorder classes, with more attention
  to connection state, closing connections on certain errors, retrying
  operations under certain conditions, and especially by changing the
  postgres recorders to obtain 'EXCLUSIVE' mode table lock when inserting
  events.
* Obtaining the table lock in PostgreSQL avoids interleaving of
  inserts between commits, which avoids event notifications from being
  committed with lower notification IDs than event notifications that
  have already been committed, and thereby prevents readers who are
  tailing the notification log of an application from missing event
  notifications for this reason.
* Added various environment variable options:

  * for sqlite a lock timeout option; and
  * for postgres a max connection age option which allows connections
    over a certain age to be closed when idle, a connection pre-ping option,
    a lock timeout option, and an option to timeout sessions idle in transaction
    so that locks can be released even if the database client has somehow
    ceased to continue its interactions with the server in a way that
    leave the session open.

* Improved the exception classes, to follow the standard Python DBAPI class names,
  and to encapsulate errors from drivers with library errors following this standard.
* Added methods to notification log and reader classes to allow notifications
  to be selected directly.
* Changed Follower class to select() rather than read() notifications.
* Supported defining initial version number of aggregates on aggregate class
  (with INITIAL_VERSION attribute).


Version 9.0.3 (released 17 May 2021)
--------------------------------------

* Changed PostgreSQL queries to use transaction class context manager
  (transactions were started and not closed).
* Added possibility to specify a port for Postgres (thanks to Valentin Dion).
* Added \*\*kwargs to Application.save() method signature, so other things can be
  passed down the stack.
* Fixed reference in installing.rst (thanks to Karl Heinrichmeyer).
* Made properties out of aggregate attributes: 'modified_on' and 'version'.
* Improved documentation.

Version 9.0.2 (released 16 April 2021)
--------------------------------------

* Fixed issue with type hints in PyCharm v2021.1 for methods decorated with the @event decorator.


Version 9.0.1 (released 29 March 2021)
--------------------------------------

* Improved documentation.
* Moved cipher base class to avoid importing cipher module.


Version 9.0.0 (released 13 March 2021)
--------------------------------------

First release of the distilled version of the library. Compared with
previous versions, the code and documentation are much simpler. This
version focuses directly on expressing the important concerns, without
the variations and alternatives that had been accumulated over the past
few years of learning and pathfinding.

* The highlight is the new :ref:`declarative syntax <Declarative syntax>`
  for event-sourced domain models.

* Dedicated persistence modules for SQLite and PostgresSQL have been
  introduced. Support for SQLAlchemy and Django, and other databases,
  has been removed. The plan is to support these in separate package
  distributions. The default "plain old Python object" infrastructure
  continues to exist, and now offers event storage and retrieval
  performance of around 20x the speed of using PostgreSQL and around
  4x the speed of using SQLite in memory.

* The event storage format is more efficient, because originator IDs and
  originator versions are removed from the stored event state before
  serialisation, and then reinstated on serialisation.

* Rather than the using "INSERT SELECT MAX" SQL statements, database
  sequences are used to generate event notifications. This avoids table
  conflicts that sometimes caused exceptions and required retries when
  storing events. Although this leads to notification ID sequences that
  may have gaps, the use of sequences means there is still no risk of
  event notifications being inserted in the gaps after later event
  notifications have been processed, which was the motivation for using
  gapless sequences in previous versions. The notification log and log
  reader classes have been adjusted to support the possible existence of
  gaps in the notification log sequence.

* The transcoder is more easily extensible, with the new style for defining
  and registering individual transcoding objects to support individual types
  of object that are not supported by default.

* Domain event classes have been greatly simplified, with the deep hierarchy
  of entity and event classes removed in favour of the simple aggregate base
  class.

* The repository class has been changed to provide a single get() method. It no
  longer supports the Python "indexing" square-bracket syntax, so that there is
  just one way to get an aggregate regardless of whether the requested version
  is specified or not.

* Application configuration of persistence infrastructure is now driven by
  environment variables rather than constructor parameters, leading to a
  simpler interface for application object classes. The mechanism for storing
  aggregates has been simplified, so that aggregates are saved using the
  application "save" method. A new "notify" method has been added to the
  application class, to support applications that need to know when new
  events have just been recorded.

* The mechanism by which aggregates published their events and a
  "persistence subscriber" subscribed and persisted published domain events
  has been completely removed, since aggregates that are saved always need
  some persistence infrastructure to store the events, and it is the
  responsibility of the application to bring together the domain model and
  infrastructure, so that when an aggregate can be saved there is always
  an application.

* Process application policy methods are now given a process event object
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

* The system runners have been reduced to the single-threaded and
  multi-threaded runners, with support for running with Ray and gRPC
  and so on removed (the plan being to support these in separate package
  distributions).

* The core library now depends only on the PythonStandard Library, except for
  the optional extra dependencies on a cryptographic library (PyCryptodome)
  and a PostgresSQL driver (psycopg2), and the dependencies of development tools.

* The test suite is now much faster to run (several seconds rather than several
  minutes for the previous version). These changes make the build time on CI
  services much quicker (around one minute, rather than nearly ten minutes for
  the previous version). And these changes make the library more approachable
  and fun for users and library developers.

* Test coverage has been increased to 100% line and branch coverage.

* Added mypy and flake8 checking.

* The documentation has been rewritten to focus more on usage of the library code,
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

* Added gRPC runner.
* Improved Django record manager, so that it supports
  setting notification log IDs in the application like the SQLAlchemy
  record manager (this optionally avoids use of the "insert select max"
  statement and thereby makes it possible to exclude domain events from
  the notification log at the risk of non-gapless notification log
  sequences).
* Also improved documentation.


Version 8.2.5 (released 22 Dec 2020)
--------------------------------------

* Increased versions of dependencies on requests, Django, Celery, PyMySQL.

Version 8.2.4 (released 12 Nov 2020)
--------------------------------------

* Fixed issue with using Oracle database, where a trailing semicolon
  in an SQL statement caused the "invalid character" error (ORA-00911).

Version 8.2.3 (released 19 May 2020)
--------------------------------------

* Improved interactions with process applications in RayRunner
  so that they have the same style as interactions with process
  applications in other runners. This makes the RayRunner more
  interchangeable with the other runners, so that system client
  code can be written to work with any runner.


Version 8.2.2 (released 16 May 2020)
--------------------------------------

* Improved documentation.
* Updated dockerization for local development.
* Added Makefile, to setup development environment,
  to build and run docker containers, to run the test suite, to
  format the code, and to build the docs.
* Reformatted the code.


Version 8.2.1 (released 11 March 2020)
--------------------------------------

* Improved documentation.


Version 8.2.0 (released 10 March 2020)
--------------------------------------

* Added optional versioning of domain events and entities, so that
  domain events and entity snapshots can be versioned and old
  versions of state can be upcast to new versions.
* Added optional correlation and causation IDs for domain events,
  so that a story can be traced through a system of applications.
* Added AxonApplication and AxonRecordManager so that Axon Server can
  be used as an event store by event-sourced applications.
* Added RayRunner, which allows a system of applications to be run with
  the Ray framework.


Version 8.1.0 (released 11 January 2020)
----------------------------------------

* Improved documentation.
* Improved transcoding (e.g. tuples are encoded as tuples also within other collections).
* Added event hash method name to event attributes, so that event hashes
  created with old version of event hashing can still be checked.
* Simplified repository base classes (removed "event player" class).


Version 8.0.0 (released 7 December 2019)
----------------------------------------

* The storage of event state has been changed from strings to bytes. Previously state
  bytes were encoded with base64 before being saved as strings, which adds 33% to the
  size of each stored state. This is definitely a backward incompatible change.
  Attention will need to be paid to one of two alternatives. One alternative is to
  migrate your stored events (the state field), either from being stored as plaintext
  strings to being stored as plaintext bytes (you need to encode as utf-8), or from
  being stored as ciphertext bytes encoded with base64 decoded as utf-8 to being stored
  as ciphertext bytes (you need to encode as utf-8 and decode base64). The other alternative
  is to carry on using the same database schema, define custom stored event record classes
  in your project (copied from the previous version of the library), and extend the record
  manager to convert the bytes to strings and back. A later version of this library may
  bring support for one or both of these options, so if this change presents a
  challenge, please hold off from upgrading, and discuss your situation with the
  project developer(s). There is nothing wrong with the previous version, and you
  can continue to use it.

* Other backward incompatible changes involve renaming a number of methods, and
  moving classes and also modules (for example, the system modules have been moved
  from the applications package to a separate package). Please see the commit log
  for all the details.

* Compression of event state is now an option, independently
  of encryption, and compression is now configurable (defaults to zlib module,
  other compressors can be used).

* This version also brings improved and expanded transcoding, additional type
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

* Version 7.x series refined the "process and system" code.


Version 7.2.4 (released 9 Oct 2019)
------------------------------------

* Fixed an issue in running the test suite.


Version 7.2.3 (released 9 Oct 2019)
------------------------------------

* Fixed a bug in MultiThreadedRunner.


Version 7.2.2 (released 6 Oct 2019)
------------------------------------

* Improved documentation for "reliable projections".


Version 7.2.1 (released 6 Oct 2019)
------------------------------------

* Improved support for "reliable projections",
  which allows custom records to be deleted (previously only
  create and update was supported). The documentation for
  "reliable projections" was improved. The previous code
  snippet, which was merely suggestive, was replaced by a
  working example.


Version 7.2.0 (released 1 Oct 2019)
------------------------------------

* Add support for "reliable projections" into custom
  ORM objects that can be coded as process application policies.

* Also a few other issues were resolved: avoiding importing Django models from library
  when custom models are being used to store events prevents model conflicts;
  fixed multiprocess runner to work when an application is not being followed
  by another; process applications now reflect off the sequenced item tuple when
  reading notifications so that custom field names are used.


Version 7.1.6 (released 2 Aug 2019)
------------------------------------

* Fixed an issue with the notification log reader. The notification
  log reader was sometimes using a "fast path" to get all the notifications without
  paging through the notification log using the linked sections. However, when there
  were too many notification, this failed to work. A few adjustments were made
  to fix the performance and robustness and configurability of the notification
  log reading functionality.


Version 7.1.5 (released 26 Jul 2019)
------------------------------------

* Improved the library documentation with better links to
  module reference pages.
* The versions of dependencies were also updated,
  so that all versions of dependencies are the current stable versions
  of the package distributions on PyPI. In particular, requests was
  updated to a version that fixes a security vulnerability.


Version 7.1.4 (released 10 Jul 2019)
------------------------------------

* Improved the library documentation.


Version 7.1.3 (released 4 Jul 2019)
------------------------------------

* Improved the domain model layer documentation.


Version 7.1.2 (released 26 Jun 2019)
------------------------------------

* Fixed method 'construct_app()' on class 'System' to set 'setup_table'
  on its process applications using the system's value of 'setup_tables'.
* Updated version of dependency of SQLAlchemy-Utils.


Version 7.1.1 (released 21 Jun 2019)
------------------------------------

* Added 'Support options' and 'Contributing' sections to the documentation.


Version 7.1.0 (released 11 Jun 2019)
------------------------------------

* Improved structure to the documentation.


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
