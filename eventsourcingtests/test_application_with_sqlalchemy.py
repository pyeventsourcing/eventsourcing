from eventsourcing.application.example.with_sqlalchemy import ExampleApplicationWithSQLAlchemy
from eventsourcing.infrastructure.stored_events.transcoders import ObjectJSONEncoder, ObjectJSONDecoder
from eventsourcingtests.example_application_testcase import ExampleApplicationTestCase


class TestApplicationWithSQLAlchemy(ExampleApplicationTestCase):

    def test_application_with_sqlalchemy(self):
        # Setup the example application, use it as a context manager.
        with ExampleApplicationWithSQLAlchemy(db_uri='sqlite:///:memory:', json_encoder_cls=ObjectJSONEncoder, json_decoder_cls=ObjectJSONDecoder) as app:
            self.assert_is_example_application(app)
