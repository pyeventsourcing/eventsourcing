from eventsourcing.application.policies import PersistencePolicy
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


class SimpleApplication(object):
    def __init__(self, event_store):
        self.event_store = event_store

        # Construct a persistence policy.
        self.persistence_policy = PersistencePolicy(
            event_store=self.event_store
        )

    def construct_repository(self, entity_class):
        return EventSourcedRepository(
            event_store=self.event_store,
            mutator=entity_class._mutate
        )

    def close(self):
        self.persistence_policy.close()
