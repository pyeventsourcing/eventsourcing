from eventsourcing.infrastructure.datastore import Datastore, DatastoreSettings


class DjangoDatastore(Datastore):
    def __init__(self, **kwargs):
        super(DjangoDatastore, self).__init__(**kwargs)

    def setup_connection(self):
        pass

    def setup_tables(self, tables=None):
        pass

    def drop_tables(self):
        pass

    def truncate_tables(self):
        pass

    def close_connection(self):
        pass


class DjangoSettings(DatastoreSettings):
    pass
