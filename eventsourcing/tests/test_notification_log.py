# from eventsourcing.domain.model.notificationlog import NotificationLog
# from eventsourcing.infrastructure.event_sourced_repos.timebucketedlog_repo import TimebucketedlogRepo
# from eventsourcing.infrastructure.event_sourced_repos.notificationlog_repo import NotificationLogRepo
# from eventsourcing.infrastructure.event_sourced_repos.sequence import SequenceRepo
# from eventsourcing.infrastructure.notification_log import NotificationLogReader, append_item_to_notification_log
# from eventsourcing.tests.sequenced_item_tests.test_cassandra_active_record_strategy import \
#     WithCassandraActiveRecordStrategies
# from eventsourcing.tests.sequenced_item_tests.test_sqlalchemy_active_record_strategy import \
#     WithSQLAlchemyActiveRecordStrategies
# from eventsourcing.tests.sequenced_item_tests.base import WithPersistencePolicy
#
#
# # Todo: Read from subsequent sequences if slice.stop goes beyond the end of the sequence.
#
#
# class NotificationLogTestCase(WithPersistencePolicy):
#
#     def test_entity_lifecycle(self):
#         notification_log_repo = NotificationLogRepo(self.timestamped_entity_event_store)
#
#         notification_log = notification_log_repo.get_or_create(
#             log_name='log1',
#             sequence_size=2,
#         )
#
#         self.assertIsInstance(notification_log, NotificationLog)
#
#         item1 = 'item1'
#
#         log_repo = TimebucketedlogRepo(self.timestamped_entity_event_store)
#         sequence_repo = SequenceRepo(event_store=self.versioned_entity_event_store)
#
#         append_item_to_notification_log(notification_log, item1, sequence_repo, log_repo, self.event_store)
#
#         notification_log_reader = NotificationLogReader(
#             notification_log=notification_log,
#             sequence_repo=sequence_repo,
#             log_repo=log_repo,
#             event_store=self.event_store,
#         )
#         self.assertEqual(notification_log_reader[0], item1)
#
#         item2 = 'item2'
#         append_item_to_notification_log(notification_log, item2, sequence_repo, log_repo, self.event_store)
#
#         self.assertEqual(notification_log_reader[1], item2)
#
#         item3 = 'item3'
#         item4 = 'item4'
#         item5 = 'item5'
#         append_item_to_notification_log(notification_log, item3, sequence_repo, log_repo, self.event_store)
#         append_item_to_notification_log(notification_log, item4, sequence_repo, log_repo, self.event_store)
#         append_item_to_notification_log(notification_log, item5, sequence_repo, log_repo, self.event_store)
#
#         self.assertEqual(notification_log_reader[2], item3)
#         self.assertEqual(notification_log_reader[3], item4)
#         self.assertEqual(notification_log_reader[4], item5)
#
#         self.assertEqual(notification_log_reader[0:2], [item1, item2])
#         self.assertEqual(notification_log_reader[2:4], [item3, item4])
#
#         # Check stop value is handled properly.
#         self.assertEqual(notification_log_reader[2:3], [item3])
#
#         # Index too large.
#         with self.assertRaises(IndexError):
#             notification_log_reader[5]
#
#         # Negative index.
#         with self.assertRaises(IndexError):
#             notification_log_reader[-1]
#
#         # Incomplete slice.
#         with self.assertRaises(IndexError):
#             notification_log_reader[1:]
#
#         # Incomplete slice.
#         with self.assertRaises(IndexError):
#             notification_log_reader[:1]
#
#         # Negative start.
#         with self.assertRaises(IndexError):
#             notification_log_reader[-1:0]
#
#         with self.assertRaises(IndexError):
#             # Slice has negative stop.
#             notification_log_reader[0:-1]
#
#         with self.assertRaises(IndexError):
#             # Slice crosses sequences.
#             notification_log_reader[0:4]
#
#         notification_log_reader[0:1:None]
#         with self.assertRaises(IndexError):
#             # Slice has a step value.
#             notification_log_reader[0:1:1]
#
#         # Add some more items.
#         for i in range(10):
#             item = 'boo{}'.format(i)
#             append_item_to_notification_log(notification_log, item, sequence_repo, log_repo, self.event_store)
#
#             # Check the length.
#             notification_log_index = 5 + i
#             self.assertEqual(len(notification_log_reader), notification_log_index + 1)
#
#             # Check the message.
#             self.assertEqual(notification_log_reader[notification_log_index], item)
#
#
# class TestNotificationLogWithCassandra(WithCassandraActiveRecordStrategies, NotificationLogTestCase):
#     pass
#
#
# class TestNotificationLogWithSQLAlchemy(WithSQLAlchemyActiveRecordStrategies, NotificationLogTestCase):
#     pass
