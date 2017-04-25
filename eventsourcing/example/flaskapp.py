from flask import Flask

from eventsourcing.example.application import get_example_application, init_example_application
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy, \
    IntegerSequencedItemRecord
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings

application = Flask(__name__)


@application.route("/")
def hello():
    app = get_example_application()
    entity_id = app.create_new_example(foo='Hello There!').id
    entity = app.example_repository[entity_id]
    return "<h1 style='color:blue'>{}</h1>".format(entity.foo)


def init_example_application_with_sqlalchemy(session):
    active_record_strategy = SQLAlchemyActiveRecordStrategy(
        active_record_class=IntegerSequencedItemRecord,
        session=session,
    )
    init_example_application(
        integer_sequenced_active_record_strategy=active_record_strategy
    )


if __name__ == "__main__":
    # Initialise the process.
    uri = 'sqlite:///:memory:'
    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri=uri),
        tables=(IntegerSequencedItemRecord,)
    )
    datastore.setup_connection()
    datastore.setup_tables()
    init_example_application_with_sqlalchemy(datastore.db_session)

    # Run the application.
    application.run(host='0.0.0.0', port=5001)
