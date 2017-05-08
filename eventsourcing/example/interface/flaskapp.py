import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils.types.uuid import UUIDType

from eventsourcing.example.application import get_example_application, init_example_application
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy


# Read DB URI from environment.
uri = os.environ.get('DB_URI', 'sqlite:///:memory:')


# Construct Flask application.
application = Flask(__name__)
application.config['SQLALCHEMY_DATABASE_URI'] = uri
application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# Define database connection.
db = SQLAlchemy(application)


# Define database tables.
class IntegerSequencedItem(db.Model):
    __tablename__ = 'integer_sequenced_items'
    sequence_id = db.Column(UUIDType(), primary_key=True)
    position = db.Column(db.BigInteger(), primary_key=True)
    topic = db.Column(db.String(255))
    data = db.Column(db.Text())
    __table_args__ = db.Index('index', 'sequence_id', 'position'),


# Construct eventsourcing application.
@application.before_first_request
def init_example_application_with_sqlalchemy():
    init_example_application(
        entity_active_record_strategy=SQLAlchemyActiveRecordStrategy(
            active_record_class=IntegerSequencedItem,
            session=db.session,
        )
    )


# Define Web application.
@application.route("/")
def hello():
    app = get_example_application()
    entity_id = app.create_new_example(foo='Hello There!').id
    entity = app.example_repository[entity_id]
    return "<h1 style='color:blue'>{}</h1>".format(entity.foo)


# Run directly, with uWSGI, or otherwise as a WSGI application.
#
# uwsgi -H PATH_TO_VIRTUALENV --master --processes 4 --threads 2 --wsgi-file PATH_TO_THIS_FILE --http :5001
#
if __name__ == "__main__":
    # Create tables.
    db.create_all()

    # Run the application.
    application.run(host='0.0.0.0', port=5001)
