# from eventsourcing.infrastructure.storedevents.with_cassandra2 import Cassandra2StoredEventRepository, \
#     setup_cassandra_connection, get_cassandra_setup_params, create_cassandra2_keyspace_and_tables, \
#     drop_cassandra2_keyspace
# from eventsourcing.tests.base import AbstractTestCase
#
#
# class Cassandra2TestCase(AbstractTestCase):
#
#     def setUp(self):
#         super(Cassandra2TestCase, self).setUp()
#         create_cassandra2_keyspace_and_tables()
#
#     def tearDown(self):
#         drop_cassandra2_keyspace()
#         # shutdown_cassandra_connection()
#         super(Cassandra2TestCase, self).tearDown()
#
#
# class Cassandra2Repo2TestCase(Cassandra2TestCase):
#
#     def setUp(self):
#         setup_cassandra_connection(*get_cassandra_setup_params())
#         super(Cassandra2Repo2TestCase, self).setUp()
#
#     @property
#     def stored_event_repo(self):
#         try:
#             return self._stored_event_repo
#         except AttributeError:
#             stored_event_repo = Cassandra2StoredEventRepository(
#                 always_write_entity_version=True,
#                 always_check_expected_version=True,
#             )
#             self._stored_event_repo = stored_event_repo
#             return stored_event_repo
