import os
from uuid import uuid4

os.environ['DJANGO_SETTINGS_MODULE'] = 'eventsourcing.tests.djangoproject.djangoproject.settings'

import django

django.setup()

from eventsourcing.infrastructure.django.datastore import DjangoDatastore, DjangoSettings
from eventsourcing.infrastructure.django.models import IntegerSequencedRecord

from eventsourcing.tests.datastore_tests.base import AbstractDatastoreTestCase, DatastoreTestCase
from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import DjangoTestCase


class DjangoDatastoreTestCase(AbstractDatastoreTestCase):
    contiguous_record_ids = True

    def construct_datastore(self):
        return DjangoDatastore(
            settings=DjangoSettings()
        )


class TestDjangoDatastore(DjangoDatastoreTestCase, DatastoreTestCase, DjangoTestCase):
    def list_records(self):
        query = IntegerSequencedRecord.objects.all()
        return list(query)

    def create_record(self):
        record = IntegerSequencedRecord(
            sequence_id=uuid4(),
            position=0,
            topic='topic',
            data='{}'
        )
        record.save()
        return record
