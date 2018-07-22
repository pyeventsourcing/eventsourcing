from django.db import connection

from eventsourcing.application import command, process, simple, snapshotting

from eventsourcing.infrastructure.django.manager import DjangoRecordManager
from eventsourcing.infrastructure.django.models import StoredEventRecord, EntitySnapshotRecord


class WithDjango(simple.Application):
    record_manager_class = DjangoRecordManager
    stored_event_record_class = StoredEventRecord
    snapshot_record_class = EntitySnapshotRecord

    @classmethod
    def reset_connection_after_forking(cls):
        connection.close()
        import django
        django.setup()


Application = WithDjango


# Todo: Remove these other classes.
class ApplicationWithSnapshotting(snapshotting.ApplicationWithSnapshotting,
                                  Application): pass

class ProcessApplication(process.ProcessApplication,
                         Application): pass
