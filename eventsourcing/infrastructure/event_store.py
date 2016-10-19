import six

from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.infrastructure.stored_events.base import StoredEventRepository
from eventsourcing.infrastructure.stored_events.transcoders import serialize_domain_event, deserialize_domain_event


class EventStore(object):

    serialize_without_json = False
    serialize_with_uuid1 = True

    def __init__(self, stored_event_repo, json_encoder_cls=None, json_decoder_cls=None, cipher=None, always_encrypt=False):
        assert isinstance(stored_event_repo, StoredEventRepository), stored_event_repo
        self.stored_event_repo = stored_event_repo
        self.json_encoder_cls = json_encoder_cls
        self.json_decoder_cls = json_decoder_cls
        self.cipher = cipher
        self.always_encrypt = always_encrypt

    def append(self, domain_event):
        assert isinstance(domain_event, DomainEvent)
        # Serialize the domain event.
        stored_event = self.serialize(domain_event)

        # Append the stored event to the stored event repo.
        self.stored_event_repo.append(new_stored_event=stored_event, new_version_number=domain_event.entity_version)

    def get_entity_events(self, stored_entity_id, after=None, until=None, limit=None, is_ascending=True,
                          page_size=None):
        # Get the events that have been stored for the entity.
        if page_size:
            stored_events = self.stored_event_repo.iterate_entity_events(
                stored_entity_id=stored_entity_id,
                after=after,
                until=until,
                limit=limit,
                is_ascending=is_ascending,
                page_size=page_size
            )
        else:
            stored_events = self.stored_event_repo.get_entity_events(
                stored_entity_id=stored_entity_id,
                after=after,
                until=until,
                limit=limit,
                query_ascending=is_ascending,
                results_ascending=is_ascending,
            )

        # Deserialize all the stored event objects into domain event objects.
        return six.moves.map(self.deserialize, stored_events)

    def get_most_recent_event(self, stored_entity_id, until=None):
        """Returns last event for given stored entity ID.

        :rtype: DomainEvent, NoneType
        """
        stored_event = self.stored_event_repo.get_most_recent_event(stored_entity_id, until=until)
        return None if stored_event is None else self.deserialize(stored_event)

    def get_entity_version(self, stored_entity_id, version):
        return self.stored_event_repo.get_entity_version(stored_entity_id=stored_entity_id, version_number=version)


    def serialize(self, domain_event):
        """
        Returns a stored event from a domain event.

        :rtype: StoredEvent

        """
        return serialize_domain_event(
            domain_event,
            json_encoder_cls=self.json_encoder_cls,
            without_json=self.serialize_without_json,
            with_uuid1=self.serialize_with_uuid1,
            cipher=self.cipher,
            always_encrypt=self.always_encrypt,
        )

    def deserialize(self, stored_event):
        """
        Returns a domain event from a stored event.

        :rtype: DomainEvent
        """
        return deserialize_domain_event(
            stored_event,
            json_decoder_cls=self.json_decoder_cls,
            without_json=self.serialize_without_json,
            with_uuid1=self.serialize_with_uuid1,
            cipher=self.cipher,
            always_encrypt=self.always_encrypt,
        )
