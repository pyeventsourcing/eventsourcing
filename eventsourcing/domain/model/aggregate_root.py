from eventsourcing.domain.model.entity import MismatchedOriginatorIDError, MismatchedOriginatorVersionError, \
    MutatorRequiresTypeNotInstance, TimestampedVersionedEntity, entity_mutator, singledispatch
from eventsourcing.domain.model.events import DomainEvent, EventWithTimestamp, publish


class AggregateEvent(EventWithTimestamp, DomainEvent):
    """
    Aggregate event supertype.
    """

    def __init__(self, aggregate_id, aggregate_version, **kwargs):
        super(AggregateEvent, self).__init__(**kwargs)
        self.__dict__['aggregate_id'] = aggregate_id
        self.__dict__['aggregate_version'] = aggregate_version

    @property
    def aggregate_id(self):
        return self.__dict__['aggregate_id']

    @property
    def aggregate_version(self):
        return self.__dict__['aggregate_version']


class AggregateCreated(AggregateEvent):
    """
    Published when an aggregate is created.
    """

    def __init__(self, aggregate_version=0, **kwargs):
        super(AggregateCreated, self).__init__(aggregate_version=aggregate_version, **kwargs)


class AttributeChanged(AggregateEvent):
    """
    Published when an aggregate is created.
    """

    def __init__(self, aggregate_version=0, **kwargs):
        super(AttributeChanged, self).__init__(aggregate_version=aggregate_version, **kwargs)


class AggregateDiscarded(AggregateEvent):
    """
    Published when an aggregate is discarded.
    """

    def __init__(self, **kwargs):
        super(AggregateDiscarded, self).__init__(**kwargs)


class AggregateRoot(TimestampedVersionedEntity):
    """
    Example root entity of aggregate.
    """

    def __init__(self, aggregate_id, aggregate_version=0, **kwargs):
        super(AggregateRoot, self).__init__(
            entity_id=aggregate_id, entity_version=aggregate_version, **kwargs
        )
        self._pending_events = []

    def _validate_originator_id(self, event):
        """
        Checks the event's entity ID matches this entity's ID.
        """
        if self._id != event.aggregate_id:
            raise MismatchedOriginatorIDError(
                "Aggregate root ID '{}' not equal to event's aggregate ID '{}'"
                "".format(self.id, event.aggregate_id)
            )

    def _validate_originator_version(self, event):
        """
        Checks the event's entity version matches this entity's version.
        """
        if self._version != event.aggregate_version:
            raise MismatchedOriginatorVersionError(
                ("Event originated from aggregate at version {}, but aggregate is currently at version {}. "
                 "Event type: '{}', aggregate type: '{}', aggregate ID: '{}'"
                 "".format(self._version, event.aggregate_version,
                           type(event).__name__, type(self).__name__, self._id)
                 )
            )

    def _change_attribute(self, name, value):
        self._assert_not_discarded()
        event_class = getattr(self, 'AttributeChanged', AttributeChanged)
        event = event_class(name=name, value=value, aggregate_id=self._id, aggregate_version=self._version)
        self._apply(event)
        self._pending_events.append(event)

    def discard(self):
        assert not self._is_discarded
        event = AggregateDiscarded(aggregate_id=self.id, aggregate_version=self.version)
        self._apply(event)
        self._pending_events.append(event)

    def save(self):
        publish(self._pending_events[:])
        self._pending_events = []

    @staticmethod
    def _mutator(event, initial):
        return aggregate_mutator(event, initial)


@singledispatch
def aggregate_mutator(event, self):
    return entity_mutator(event, self)


@aggregate_mutator.register(AggregateCreated)
def created_mutator(event, cls):
    assert isinstance(event, AggregateCreated), event
    if not isinstance(cls, type):
        msg = ("Mutator for Created event requires entity type not instance: {} "
               "(event entity id: {}, event type: {})"
               "".format(type(cls), event.aggregate_id, type(event)))
        raise MutatorRequiresTypeNotInstance(msg)
    assert issubclass(cls, AggregateRoot), cls
    try:
        self = cls(**event.__dict__)
    except TypeError as e:
        raise TypeError("Class {} {}. Given {} from event type {}".format(cls, e, event.__dict__, type(event)))
    self._increment_version()
    return self


@aggregate_mutator.register(AttributeChanged)
def attribute_changed_mutator(event, self):
    assert isinstance(self, TimestampedVersionedEntity), self
    self._validate_originator(event)
    setattr(self, event.name, event.value)
    self._last_modified_on = event.timestamp
    self._increment_version()
    return self


@aggregate_mutator.register(AggregateDiscarded)
def discarded_mutator(event, self):
    assert isinstance(self, TimestampedVersionedEntity), self
    self._validate_originator(event)
    self._is_discarded = True
    self._increment_version()
    return None
