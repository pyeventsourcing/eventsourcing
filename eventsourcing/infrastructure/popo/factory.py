from eventsourcing.infrastructure.factory import InfrastructureFactory
from eventsourcing.infrastructure.popo.manager import PopoRecordManager


class PopoInfrastructureFactory(InfrastructureFactory):
    record_manager_class = PopoRecordManager
