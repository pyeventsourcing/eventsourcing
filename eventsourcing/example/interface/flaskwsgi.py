import eventsourcing.example.interface.flaskapp


# Todo: Investigate why removing this file breaks python3.3.
# For some reason, this file is needed to run flaskapp.py
# with uWSGI and python3.3.
#
application = eventsourcing.example.interface.flaskapp.application
