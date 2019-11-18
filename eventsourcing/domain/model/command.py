from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.types import T_en


class Command(AggregateRoot):
    def __init__(self, **kwargs):
        super(Command, self).__init__(**kwargs)
        self._is_done = False

    class Event(AggregateRoot.Event[T_en]):
        pass

    class Created(Event[T_en], AggregateRoot.Created[T_en]):
        pass

    class AttributeChanged(Event[T_en], AggregateRoot.AttributeChanged[T_en]):
        pass

    class Discarded(Event[T_en], AggregateRoot.Discarded[T_en]):
        pass

    @property
    def is_done(self):
        return self._is_done

    def done(self):
        self.__trigger_event__(self.Done)

    class Done(Event):
        def mutate(self, obj: "Command") -> None:
            obj._is_done = True
