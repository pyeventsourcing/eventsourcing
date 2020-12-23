from eventsourcing.storedevent import StoredEvent


class Notification(StoredEvent):
    id: int
