from eventsourcing.domain import ImmutableObject


class Tracking(ImmutableObject):
    application_name: str
    notification_id: int
