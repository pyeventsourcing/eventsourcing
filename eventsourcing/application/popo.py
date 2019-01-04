from eventsourcing.application.simple import Application
from eventsourcing.infrastructure.popo.factory import PopoInfrastructureFactory
from eventsourcing.infrastructure.popo.mapper import SequencedItemMapperForPopo
from eventsourcing.infrastructure.popo.records import StoredEventRecord


class PopoApplication(Application):
    infrastructure_factory_class = PopoInfrastructureFactory
    sequenced_item_mapper_class = SequencedItemMapperForPopo
    stored_event_record_class = StoredEventRecord
