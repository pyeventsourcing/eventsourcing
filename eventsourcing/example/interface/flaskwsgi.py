import os

# Just to make this module appear in the docs.
try:
    from uwsgidecorators import postfork
except ImportError:
    postfork = lambda object: object

import eventsourcing.example.interface.flaskapp
from eventsourcing.example.interface.flaskapp import init_example_application_with_sqlalchemy
from eventsourcing.infrastructure.sqlalchemy.activerecords import IntegerSequencedItemRecord
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings

# Todo: Investigate why removing this file breaks python3.3.
# For some reason, this file is needed to run flaskapp.py
# with uWSGI and python3.3.
#
application = eventsourcing.example.interface.flaskapp.application


# Trigger initialising the process after forking.
@postfork
def init_process():
    # Initialise the database.
    datastore = SQLAlchemyDatastore(
        settings=SQLAlchemySettings(uri=os.getenv('DB_URI')),
        tables=(IntegerSequencedItemRecord,)
    )
    datastore.setup_connection()

    # Initialise the application.
    init_example_application_with_sqlalchemy(datastore.session)
