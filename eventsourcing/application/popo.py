from eventsourcing.application.simple import ApplicationWithConcreteInfrastructure
from eventsourcing.infrastructure.popo.factory import PopoInfrastructureFactory
from eventsourcing.infrastructure.popo.mapper import SequencedItemMapperForPopo
from eventsourcing.infrastructure.popo.records import StoredEventRecord


class PopoApplication(ApplicationWithConcreteInfrastructure):
    infrastructure_factory_class = PopoInfrastructureFactory
    sequenced_item_mapper_class = SequencedItemMapperForPopo
    stored_event_record_class = StoredEventRecord
