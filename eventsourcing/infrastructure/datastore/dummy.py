from eventsourcing.infrastructure.datastore.base import Datastore, DatastoreSettings


class DummyDatastore(Datastore):

    def __init__(self):
        super(DummyDatastore, self).__init__(settings=DatastoreSettings(), tables=())

    def setup_connection(self): pass

    def setup_tables(self): pass

    def drop_connection(self): pass

    def drop_tables(self): pass
