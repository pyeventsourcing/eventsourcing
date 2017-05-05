# import datetime
# import json
# import os
# import traceback
# from multiprocessing.pool import Pool
# from time import sleep
# from uuid import uuid1, uuid4
#
# import six
#
# from eventsourcing.exceptions import ConcurrencyError, DatasourceOperationError
# from eventsourcing.infrastructure.datastore.cassandraengine import CassandraDatastore, CassandraSettings
# from eventsourcing.infrastructure.datastore.sqlalchemyorm import SQLAlchemyDatastore, SQLAlchemySettings
# from eventsourcing.infrastructure.eventstore import AbstractStoredEventRepository
# from eventsourcing.infrastructure.storedevents.cassandrarepo import CassandraStoredEventRepository, CqlStoredEvent
# from eventsourcing.infrastructure.storedevents.pythonobjectsrepo import PythonObjectsStoredEventRepository
# from eventsourcing.infrastructure.storedevents.sqlalchemyrepo import SQLAlchemyStoredEventRepository
# from eventsourcing.infrastructure.transcoding import StoredEvent
# from eventsourcing.tests.base import notquick
# from eventsourcing.tests.datastore_tests.test_cassandra import DEFAULT_KEYSPACE_FOR_TESTING
# from eventsourcing.tests.sequenced_item_tests.base import WithActiveRecordStrategies
# from eventsourcing.tests.sequenced_item_tests.test_cassandra_active_record_strategy import \
#     WithCassandraActiveRecordStrategies
# from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
#     WithSQLAlchemyActiveRecordStrategies
#
#
# class OptimisticConcurrencyControlTestCase(WithActiveRecordStrategies):
#     @notquick
#     def test_optimistic_concurrency_control(self):
#         """Appends lots of events, but with a pool of workers
#         all trying to add the same sequence of events.
#         """
#         # Start a pool.
#         pool_size = 3
#         print("Pool size: {}".format(pool_size))
#
#         # Erm, this is only needed for SQLite database file.
#         # Todo: Maybe factor out a 'get_initargs()' method on this class,
#         # so this detail is localised to the test cases that need it.
#         if hasattr(self, 'temp_file'):
#             temp_file_name = getattr(self, 'temp_file').name
#         else:
#             temp_file_name = None
#
#         pool = Pool(
#             initializer=pool_initializer,
#             processes=pool_size,
#             initargs=(type(self.integer_sequence_active_record_strategy), temp_file_name),
#         )
#
#         # Append duplicate events to the repo, or at least try...
#         number_of_events = 40
#         self.assertGreater(number_of_events, pool_size)
#         stored_entity_id = uuid4().hex
#         sequence_of_args = [(number_of_events, stored_entity_id)] * pool_size
#         results = pool.map(append_lots_of_events_to_repo, sequence_of_args)
#         total_successes = []
#         total_failures = []
#         for result in results:
#             if isinstance(result, Exception):
#                 print(result.args[0][1])
#                 raise result
#             else:
#                 successes, failures = result
#                 assert isinstance(successes, list), result
#                 assert isinstance(failures, list), result
#                 total_successes.extend(successes)
#                 total_failures.extend(failures)
#
#         # Close the pool.
#         pool.close()
#
#         # Check each event version was written exactly once.
#         self.assertEqual(sorted([i[0] for i in total_successes]), list(range(number_of_events)))
#
#         # Check there was contention that caused at least one concurrency error.
#         set_failures = set([i[0] for i in total_failures])
#         self.assertTrue(len(set_failures))
#
#         # Check each child wrote at least one event.
#         self.assertEqual(len(set([i[1] for i in total_successes])), pool_size)
#
#         # Check each child encountered at least one concurrency error.
#         self.assertEqual(len(set([i[1] for i in total_failures])), pool_size)
#
#         # Check the repo actually has a contiguous version sequence.
#         events = self.integer_sequence_active_record_strategy.get_stored_events(stored_entity_id)
#         self.assertEqual(len(events), number_of_events)
#         version_counter = 0
#         for event in events:
#             assert isinstance(event, StoredEvent)
#             attr_values = json.loads(event.event_attrs)
#             self.assertEqual(attr_values['originator_version'], version_counter)
#             version_counter += 1
#
#         # Join the pool.
#         pool.join()
#
#     @staticmethod
#     def append_lots_of_events_to_repo(args):
#
#         num_events_to_create, stored_entity_id = args
#
#         success_count = 0
#         assert isinstance(num_events_to_create, six.integer_types)
#
#         successes = []
#         failures = []
#
#         try:
#
#             while True:
#                 # Imitate an entity getting refreshed, by getting the version of the last event.
#                 assert isinstance(worker_repo, AbstractStoredEventRepository)
#                 events = worker_repo.get_stored_events(stored_entity_id, limit=1, query_ascending=False)
#                 if len(events):
#                     current_version = json.loads(events[0].event_attrs)['originator_version']
#                     new_version = current_version + 1
#                 else:
#                     current_version = None
#                     new_version = 0
#
#                 # Stop before the version number gets too high.
#                 if new_version >= num_events_to_create:
#                     break
#
#                 pid = os.getpid()
#                 try:
#
#                     # Append an event.
#                     stored_event = StoredEvent(
#                         event_id=uuid1().hex,
#                         stored_entity_id=stored_entity_id,
#                         event_topic='topic',
#                         event_attrs=json.dumps({'a': 1, 'b': 2, 'originator_version': new_version}),
#                     )
#                     started = datetime.datetime.now()
#                     worker_repo.append(
#                         new_stored_event=stored_event,
#                         new_version_number=new_version,
#                         max_retries=10,
#                         artificial_failure_rate=0.25,
#                     )
#                 except ConcurrencyError:
#                     # print("PID {} got concurrent exception writing event at version {} at {}".format(
#                     #     pid, new_version, started, datetime.datetime.now() - started))
#                     failures.append((new_version, pid))
#                     sleep(0.01)
#                 except DatasourceOperationError:
#                     # print("PID {} got concurrent exception writing event at version {} at {}".format(
#                     #     pid, new_version, started, datetime.datetime.now() - started))
#                     # failures.append((new_version, pid))
#                     sleep(0.01)
#                 else:
#                     print("PID {} success writing event at version {} at {} in {}".format(
#                         pid, new_version, started, datetime.datetime.now() - started))
#                     success_count += 1
#                     successes.append((new_version, pid))
#                     # Delay a successful writer, to give other processes a chance to write the next event.
#                     sleep(0.03)
#
#         # Return to parent process the successes and failure, or an exception.
#         except Exception as e:
#             msg = traceback.format_exc()
#             print(" - failed to append event: {}".format(msg))
#             return Exception((e, msg))
#         else:
#             return (successes, failures)
#
#
# @notquick
# class TestOptimisticConcurrencyControlWithCassandra(WithCassandraActiveRecordStrategies,
#                                                     OptimisticConcurrencyControlTestCase):
#     pass
#
#
# class TestOptimisticConcurrencyControlWithSQLAlchemy(WithSQLAlchemyActiveRecordStrategies,
#                                                      OptimisticConcurrencyControlTestCase):
#     use_named_temporary_file = True
#
#
# worker_repo = None
#
#
# def pool_initializer(stored_repo_class, temp_file_name):
#     global worker_repo
#     worker_repo = construct_repo_for_worker(stored_repo_class, temp_file_name)
#
#
# def construct_repo_for_worker(stored_repo_class, temp_file_name):
#     if stored_repo_class is CassandraStoredEventRepository:
#         datastore = CassandraDatastore(
#             settings=CassandraSettings(default_keyspace=DEFAULT_KEYSPACE_FOR_TESTING),
#             tables=(CqlStoredEvent,)
#         )
#         datastore.drop_connection()
#         datastore.setup_connection()
#         repo = CassandraStoredEventRepository(
#             stored_event_table=CqlStoredEvent,
#             always_check_expected_version=True,
#             always_write_originator_version=True,
#         )
#     elif stored_repo_class is SQLAlchemyStoredEventRepository:
#         uri = 'sqlite:///' + temp_file_name
#         datastore = SQLAlchemyDatastore(
#             settings=SQLAlchemySettings(uri=uri),
#             tables=(StoredEventRecord,),
#         )
#         datastore.setup_connection()
#         repo = SQLAlchemyStoredEventRepository(
#             datastore=datastore,
#             stored_event_table=StoredEventRecord,
#             always_check_expected_version=True,
#             always_write_originator_version=True,
#         )
#     elif stored_repo_class is PythonObjectsStoredEventRepository:
#         repo = PythonObjectsStoredEventRepository(
#             always_check_expected_version=True,
#             always_write_originator_version=True,
#         )
#     else:
#         raise Exception("Stored repo class not yet supported in test: {}".format(stored_repo_class))
#     return repo
#
#
# def append_lots_of_events_to_repo(args):
#     return OptimisticConcurrencyControlTestCase.append_lots_of_events_to_repo(args)
