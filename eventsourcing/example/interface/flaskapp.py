import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils.types.uuid import UUIDType

from eventsourcing.example.application import get_example_application, init_example_application
from eventsourcing.infrastructure.sqlalchemy.activerecords import SQLAlchemyActiveRecordStrategy

application = Flask(__name__)

uri = os.environ.get('DB_URI', 'sqlite:///:memory:')

application.config['SQLALCHEMY_DATABASE_URI'] = uri
application.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(application)


class IntegerSequencedItemRecord(db.Model):
    __tablename__ = 'integer_sequenced_items'

    id = db.Column(db.Integer, db.Sequence('integer_sequened_item_id_seq'), primary_key=True)

    # Sequence ID (e.g. an entity or aggregate ID).
    sequence_id = db.Column(UUIDType(), index=True)

    # Position (index) of item in sequence.
    position = db.Column(db.BigInteger(), index=True)

    # Topic of the item (e.g. path to domain event class).
    topic = db.Column(db.String(255))

    # State of the item (serialized dict, possibly encrypted).
    data = db.Column(db.Text())

    # Unique constraint includes 'sequence_id' and 'position'.
    __table_args__ = db.UniqueConstraint('sequence_id', 'position',
                                         name='integer_sequenced_item_uc'),


@application.route("/")
def hello():
    app = get_example_application()
    entity_id = app.create_new_example(foo='Hello There!').id
    entity = app.example_repository[entity_id]
    return "<h1 style='color:blue'>{}</h1>".format(entity.foo)


@application.before_first_request
def init_example_application_with_sqlalchemy():
    active_record_strategy = SQLAlchemyActiveRecordStrategy(
        active_record_class=IntegerSequencedItemRecord,
        session=db.session,
    )
    init_example_application(
        entity_active_record_strategy=active_record_strategy
    )


if __name__ == "__main__":
    # Create tables.
    db.create_all()

    # Run the application.
    application.run(host='0.0.0.0', port=5001)
