from eventsourcing.examples.searchablecontent.postgres import (
    PostgresSearchableContentRecorder,
)
from eventsourcing.postgres import Factory, PostgresProcessRecorder


class SearchableContentProcessRecorder(
    PostgresSearchableContentRecorder, PostgresProcessRecorder
):
    pass


class SearchableContentInfrastructureFactory(Factory):
    process_recorder_class = SearchableContentProcessRecorder


del Factory
