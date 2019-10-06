import django
from django.db import models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

from eventsourcing.tests.sequenced_item_tests.test_django_record_manager import (
    DjangoTestCase,
)
from eventsourcing.application.django import DjangoApplication
from eventsourcing.tests.test_process import TestProcessApplication


class TestProcessWithDjango(DjangoTestCase, TestProcessApplication):
    process_class = DjangoApplication

    def test_projection_into_custom_orm_obj(self):
        super(TestProcessWithDjango, self).test_projection_into_custom_orm_obj()

    def define_projection_record_class(self):
        class ProjectionRecord(models.Model):
            uid = models.BigAutoField(primary_key=True)

            # Sequence ID (e.g. an entity or aggregate ID).
            projection_id = models.UUIDField()

            # State of the item (serialized dict, possibly encrypted).
            state = models.TextField()

            class Meta:
                db_table = "projections"
                app_label = "projections"
                managed = False

        self.projection_record_class = ProjectionRecord

    def setup_projections_table(self, process):
        from django.db import connections

        with connections["default"].schema_editor() as schema_editor:
            assert isinstance(schema_editor, BaseDatabaseSchemaEditor)
            try:
                schema_editor.delete_model(self.projection_record_class)
            except django.db.utils.ProgrammingError:
                pass

        with connections["default"].schema_editor() as schema_editor:
            assert isinstance(schema_editor, BaseDatabaseSchemaEditor)
            schema_editor.create_model(self.projection_record_class)

    def get_projection_record(
        self, projection_record_class, projection_id, record_manager
    ):
        try:
            return projection_record_class.objects.get(projection_id=projection_id)
        except projection_record_class.DoesNotExist:
            return None


del TestProcessApplication
