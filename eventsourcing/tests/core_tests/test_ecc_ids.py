from unittest import TestCase

from eventsourcing.domain.model.aggregate import AggregateRoot, BaseAggregateRoot
from eventsourcing.domain.model.entity import EntityWithECC


class MyBaseAggregateRoot(EntityWithECC, BaseAggregateRoot):
    class Event(EntityWithECC.Event, BaseAggregateRoot.Event):
        pass

    class Created(BaseAggregateRoot.Created, Event):
        pass

    class AttributeChanged(Event, BaseAggregateRoot.AttributeChanged):
        pass

    class Discarded(Event, BaseAggregateRoot.Discarded):
        pass


class TestEntityWithECC(TestCase):
    aggregate_class = MyBaseAggregateRoot

    def test(self):
        # Create first aggregate.
        aggregate1 = self.aggregate_class.__create__(application_name="app1")
        # Get first created event.
        events = aggregate1.__batch_pending_events__()
        created_event1: MyBaseAggregateRoot.Event = events[0]
        # Should have unique event ID.
        self.assertEqual(
            created_event1.event_id, "app1:{}:0".format(str(aggregate1.id))
        )
        # Should be correlated with itself.
        self.assertEqual(created_event1.correlation_id, created_event1.event_id)
        # Should be caused by nothing.
        self.assertEqual(created_event1.causation_id, None)

        # Create second aggregate, caused by processing first created event.
        aggregate2 = self.aggregate_class.__create__(
            processed_event=created_event1, application_name="app2"
        )
        # Get second created event.
        events = aggregate2.__batch_pending_events__()
        created_event2: MyBaseAggregateRoot.Event = events[0]
        # Should have unique event ID.
        self.assertEqual(
            created_event2.event_id, "app2:{}:0".format(str(aggregate2.id))
        )
        # Should be correlated with first created event.
        self.assertEqual(created_event2.correlation_id, created_event1.event_id)
        # Should be caused by first created event.
        self.assertEqual(created_event2.causation_id, created_event1.event_id)

        # Create third aggregate, caused by processing second created event.
        aggregate3 = self.aggregate_class.__create__(
            processed_event=created_event2, application_name="app3"
        )
        # Get third created event.
        events = aggregate3.__batch_pending_events__()
        created_event3: MyBaseAggregateRoot.Event = events[0]
        # Should have unique event ID.
        self.assertEqual(
            created_event3.event_id, "app3:{}:0".format(str(aggregate3.id))
        )
        # Should be correlated with first created event.
        self.assertEqual(created_event3.correlation_id, created_event1.event_id)
        # Should be caused by second created event.
        self.assertEqual(created_event3.causation_id, created_event2.event_id)

        # Trigger attribute changed event.
        aggregate3.__change_attribute__(
            name="_a", value=1, application_name="app3", processed_event=created_event3
        )
        # Get third created event.
        events = aggregate3.__batch_pending_events__()
        changed_event: MyBaseAggregateRoot.Event = events[0]
        # Should have unique event ID.
        self.assertEqual(changed_event.event_id, "app3:{}:1".format(str(aggregate3.id)))
        # Should be correlated with first created event.
        self.assertEqual(changed_event.correlation_id, created_event1.event_id)
        # Should be caused by third created event.
        self.assertEqual(changed_event.causation_id, created_event3.event_id)

        # Trigger discarded event.
        aggregate3.__discard__(application_name="app3", processed_event=changed_event)
        # Get third created event.
        events = aggregate3.__batch_pending_events__()
        discarded_event: MyBaseAggregateRoot.Event = events[0]
        # Should have unique event ID.
        self.assertEqual(
            discarded_event.event_id, "app3:{}:2".format(str(aggregate3.id))
        )
        # Should be correlated with first created event.
        self.assertEqual(discarded_event.correlation_id, created_event1.event_id)
        # Should be caused by attribute changed created event.
        self.assertEqual(discarded_event.causation_id, changed_event.event_id)


class MyAggregateRoot(AggregateRoot, EntityWithECC):
    __subclassevents__ = True


class TestMyAggregateRoot(TestEntityWithECC):
    aggregate_class = MyAggregateRoot
