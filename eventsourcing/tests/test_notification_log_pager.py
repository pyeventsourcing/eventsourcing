from eventsourcing.domain.services.notification_log import append_item_to_notification_log
from eventsourcing.infrastructure.event_sourced_repos.log_repo import LogRepo
from eventsourcing.infrastructure.event_sourced_repos.notificationlog_repo import NotificationLogRepo
from eventsourcing.infrastructure.event_sourced_repos.sequence import SequenceRepo
from eventsourcing.interface.notification_log_pager import NotificationLogPager
from eventsourcing.tests.unit_test_cases import AppishTestCase
from eventsourcing.tests.unit_test_cases_cassandra import CassandraRepoTestCase
from eventsourcing.tests.unit_test_cases_python_objects import PythonObjectsRepoTestCase
from eventsourcing.tests.unit_test_cases_sqlalchemy import SQLAlchemyRepoTestCase


class NotificationLogPagerTestCase(AppishTestCase):

    def test_pager(self):
        # Build a log.
        notification_log_repo = NotificationLogRepo(self.event_store)
        log_repo = LogRepo(self.event_store)
        sequence_repo = SequenceRepo(event_store=self.event_store)
        notification_log = notification_log_repo.get_or_create(
            log_name='log1',
            sequence_size=10,
        )
        for i in range(13):
            item = 'item{}'.format(i)
            append_item_to_notification_log(notification_log, item, sequence_repo, log_repo, self.event_store)

        # Get pages.
        pager = NotificationLogPager(notification_log, sequence_repo, log_repo, self.event_store, page_size=5)

        page = pager.get('current')
        self.assertEqual(len(page), 3, page)

        page = pager.get('1,5')
        self.assertEqual(len(page), 5, page)

        page = pager.get('6,10')
        self.assertEqual(len(page), 5, page)

        page = pager.get('11,15')
        self.assertEqual(len(page), 3, page)

        page = pager.get('16,20')
        self.assertEqual(len(page), 0, page)

        # Add some more items.
        for i in range(13, 24):
            item = 'item{}'.format(i)
            append_item_to_notification_log(notification_log, item, sequence_repo, log_repo, self.event_store)

        page = pager.get('current')
        self.assertEqual(len(page), 4, page)

        page = pager.get('11,15')
        self.assertEqual(len(page), 5, page)

        page = pager.get('16,20')
        self.assertEqual(len(page), 5, page)

        page = pager.get('21,25')
        self.assertEqual(len(page), 4, page)

        page = pager.get('26,30')
        self.assertEqual(len(page), 0, page)

    def test_sequence_size_page_size_constraints(self):
        # Build a log.
        notification_log_repo = NotificationLogRepo(self.event_store)
        notification_log = notification_log_repo.get_or_create('log1', sequence_size=10)
        log_repo = LogRepo(self.event_store)
        sequence_repo = SequenceRepo(event_store=self.event_store)
        with self.assertRaises(ValueError):
            NotificationLogPager(notification_log, sequence_repo, log_repo, self.event_store, page_size=6)

        # Check the query must match the page size.
        pager = NotificationLogPager(notification_log, sequence_repo, log_repo, self.event_store, page_size=5)
        pager.get('1,5')
        with self.assertRaises(ValueError):
            pager.get('1,2')

        # Check the query must be aligned.
        pager = NotificationLogPager(notification_log, sequence_repo, log_repo, self.event_store, page_size=5)
        pager.get('1,5')
        with self.assertRaises(ValueError):
            pager.get('2,6')


class TestNotificationLogWithPythonObjects(PythonObjectsRepoTestCase, NotificationLogPagerTestCase):
    pass


class TestNotificationLogWithCassandra(CassandraRepoTestCase, NotificationLogPagerTestCase):
    pass


class TestNotificationLogWithSQLAlchemy(SQLAlchemyRepoTestCase, NotificationLogPagerTestCase):
    pass
