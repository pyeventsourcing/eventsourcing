from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.types import T


class Command(AggregateRoot[T]):
    def __init__(self, **kwargs):
        super(Command, self).__init__(**kwargs)
        self._is_done = False

    class Event(AggregateRoot.Event[T]):
        pass

    class Created(Event[T], AggregateRoot.Created[T]):
        pass

    class AttributeChanged(Event[T], AggregateRoot.AttributeChanged[T]):
        pass

    class Discarded(Event[T], AggregateRoot.Discarded[T]):
        pass

    @property
    def is_done(self):
        return self._is_done

    def done(self):
        self.__trigger_event__(self.Done)

    class Done(Event[T]):
        def mutate(self, obj):
            obj._is_done = True
