from flask import Flask

from eventsourcing.example.application import get_application, init_application
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy, \
    SqlIntegerSequencedItem
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings

application = Flask(__name__)


@application.route("/")
def hello():
    app = get_application()
    entity_id = app.create_new_example(foo='Hello There!').id
    entity = app.example_repository[entity_id]
    return "<h1 style='color:blue'>{}</h1>".format(entity.foo)


def init_application_with_sqlalchemy(session):
    active_record_strategy = SQLAlchemyActiveRecordStrategy(
        active_record_class=SqlIntegerSequencedItem,
        session=session,
    )
    init_application(
        integer_sequenced_active_record_strategy=active_record_strategy
    )


if __name__ == "__main__":
    uri = 'sqlite:///:memory:'
    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri=uri),
    )
    datastore.setup_connection()
    datastore.setup_tables()
    init_application_with_sqlalchemy(datastore.db_session)
    application.run(host='0.0.0.0', port=5001)
