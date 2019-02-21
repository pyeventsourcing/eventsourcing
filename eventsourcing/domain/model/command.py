from eventsourcing.domain.model.aggregate import AggregateRoot


class Command(AggregateRoot):
    def __init__(self, **kwargs):
        super(Command, self).__init__(**kwargs)
        self._is_done = False

    class Event(AggregateRoot.Event):
        pass

    class Created(Event, AggregateRoot.Created):
        pass

    class AttributeChanged(Event, AggregateRoot.AttributeChanged):
        pass

    class Discarded(Event, AggregateRoot.Discarded):
        pass

    @property
    def is_done(self):
        return self._is_done

    def done(self):
        self.__trigger_event__(self.Done)

    class Done(Event):
        def mutate(self, obj):
            obj._is_done = True
