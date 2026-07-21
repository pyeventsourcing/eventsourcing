from unittest import TestCase

from eventsourcing.dataclasses import Aggregate, AggregatesApplication, Decision
from eventsourcing.domain import triggers
from eventsourcing.persistence import Tracking
from eventsourcing.projection import ApplicationSubscription
from eventsourcing.utils import get_topic


class SubscriptionFixture(Aggregate):
    class Created(Decision):
        pass

    class Next(Decision):
        pass

    @triggers(Created)
    def __init__(self) -> None:
        pass

    @triggers(Next)
    def do(self) -> None:
        pass


class TestApplicationSubscription(TestCase):
    def test(self) -> None:
        app = AggregatesApplication()

        max_notification_id = app.recorder.max_notification_id()

        aggregate = SubscriptionFixture()
        aggregate.do()
        aggregate.do()
        aggregate.do()
        app.save(aggregate)

        subscription = ApplicationSubscription(app=app, gt=max_notification_id)

        # Catch up.
        event, tracking = next(subscription)
        self.assertIsInstance(event.decision, SubscriptionFixture.Created)
        self.assertIsInstance(tracking, Tracking)
        self.assertEqual(tracking.application_name, app.name)
        if max_notification_id is not None:
            self.assertGreater(tracking.notification_id, max_notification_id)

        for event, tracking in subscription:
            self.assertIsInstance(event.decision, SubscriptionFixture.Next)
            self.assertIsInstance(tracking, Tracking)
            self.assertEqual(tracking.application_name, app.name)
            if max_notification_id is not None:
                self.assertGreater(tracking.notification_id, max_notification_id)
            if tracking.notification_id == app.recorder.max_notification_id():
                break

        max_notification_id = app.recorder.max_notification_id()

        aggregate.do()
        aggregate.do()
        aggregate.do()
        app.save(aggregate)

        # Continue.
        for event, tracking in subscription:
            self.assertIsInstance(event.decision, SubscriptionFixture.Next)
            self.assertIsInstance(tracking, Tracking)
            self.assertEqual(tracking.application_name, app.name)
            if max_notification_id is not None:
                self.assertGreater(tracking.notification_id, max_notification_id)
            if tracking.notification_id == app.recorder.max_notification_id():
                break

        # Check 'topics' are effective.
        class FilteredEvent(Decision):
            pass

        aggregate.trigger_event(FilteredEvent)
        app.save(aggregate)

        subscription = ApplicationSubscription(
            app=app,
            gt=max_notification_id,
            topics=[get_topic(FilteredEvent)],
        )

        for event, _ in subscription:
            if not isinstance(event.decision, FilteredEvent):
                self.fail(f"Got an unexpected domain event: {event.decision}")
            break
