import os
from uwsgidecorators import postfork

import eventsourcing.example.flaskapp
from eventsourcing.example.flaskapp import init_application_with_sqlalchemy
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings

application = eventsourcing.example.flaskapp.application


# Use uwsgi decorator to initialise the process.
@postfork
def init_process():
    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri=os.getenv('DB_URI')),
    )
    datastore.setup_connection()
    init_application_with_sqlalchemy(datastore.db_session)
