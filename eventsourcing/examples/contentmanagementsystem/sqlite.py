from eventsourcing.examples.searchablecontent.sqlite import (
    SQLiteSearchableContentRecorder,
)
from eventsourcing.sqlite import Factory, SQLiteProcessRecorder


class SearchableContentProcessRecorder(
    SQLiteSearchableContentRecorder, SQLiteProcessRecorder
):
    pass


class SearchableContentInfrastructureFactory(Factory):
    process_recorder_class = SearchableContentProcessRecorder


del Factory
