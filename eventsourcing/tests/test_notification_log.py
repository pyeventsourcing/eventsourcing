from eventsourcing.domain.model.notification_log import NotificationLog, create_notification_log
from eventsourcing.exceptions import LogFullError
from eventsourcing.tests.unit_test_cases import AppishTestCase
from eventsourcing.tests.unit_test_cases_cassandra import CassandraRepoTestCase
from eventsourcing.tests.unit_test_cases_python_objects import PythonObjectsRepoTestCase
from eventsourcing.tests.unit_test_cases_sqlalchemy import SQLAlchemyRepoTestCase

# Todo: An indefinitely long persistent contiguous sequence, indexed by integer sequence number,
# from which a slice (pair of integer indices) can efficiently be taken.

# 1. Contiguous sequence.

# 1.1  For a single entity ID, directly publish event with successive version number, without
# it being part of a factory, or part of an entity method. Avoid having to read all events
# just to publish the next one, but generate a contiguous sequence under a single
# stored entity ID, just like an entity would. Basically an event stream without an entity.

# 1.2  For a single entity ID, select all events after one version number until another version
# number without running them through an entity mutator.

# 1.3  Interface object that can split an archived log ID of form "x,y" into two integers,
# and query for the events between those versions, returning data that can be rendered.

# 1.4  For extending across partitions, a tree with N archived logs (above sequence) as leaves.

# 1.5  Extended interface object that can work across partitions?

# 1.6  Can navigate from start by getting first log, if full then also second log, etc. Client
# tracks where it is up to. Log entity version number gives offset in log, and log number
# gives position in archived log. Archived log paging can be smaller sized than the log
# size, with index numbers in page ID being used to identify and key into archived log.

# 1.7 Can navigate from end by getting "current" log, if has "back link" then can follow it
# until reach page with latest item.

# 1.8  In timestamp ordered persistence model, get the entity ID from the version number in the
# entity version table?


class NotificationLogTestCase(AppishTestCase):

    def _test_entity_lifecycle(self):

        # notification_log_repo = NotificationLogRepo(self.event_store)

        notification_log = create_notification_log(log_name='log1', size=5)

        self.assertIsInstance(notification_log, NotificationLog)

        item1 = 'item1'
        notification_log.add_item(item1)
        self.assertEqual(len(notification_log.items), 1)
        self.assertEqual(notification_log.items[0], item1)

        item2 = 'item2'
        notification_log.add_item(item2)
        self.assertEqual(len(notification_log.items), 2)
        self.assertEqual(notification_log.items[1], item2)

        item3 = 'item3'
        item4 = 'item4'
        item5 = 'item5'
        notification_log.add_item(item3)
        notification_log.add_item(item4)
        notification_log.add_item(item5)

        self.assertEqual(len(notification_log.items), 5, notification_log.items)

        with self.assertRaises(LogFullError):
            notification_log.add_item(item5)



class TestNotificationLogWithCassandra(CassandraRepoTestCase, NotificationLogTestCase):
    pass


class TestNotificationLogWithPythonObjects(PythonObjectsRepoTestCase, NotificationLogTestCase):
    pass


class TestNotificationLogWithSQLAlchemy(SQLAlchemyRepoTestCase, NotificationLogTestCase):
    pass
