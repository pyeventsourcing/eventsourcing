from eventsourcing.domain.model.entity import AbstractEntityRepository
from eventsourcing.exceptions import RepositoryKeyError
from eventsourcing.infrastructure.eventplayer import EventPlayer
from eventsourcing.infrastructure.snapshotting import entity_from_snapshot


class EventSourcedRepository(EventPlayer, AbstractEntityRepository):
    def __contains__(self, entity_id):
        """
        Returns a boolean value according to whether entity with given ID exists.
        """
        return self.get_entity(entity_id) is not None

    def __getitem__(self, entity_id):
        """
        Returns entity with given ID.
        """
        # # Get entity from the cache.
        # if self._use_cache:
        #     try:
        #         return self._cache[entity_id]
        #     except KeyError:
        #         pass

        # Reconstitute the entity.
        entity = self.get_entity(entity_id)

        # Never created or already discarded?
        if entity is None:
            raise RepositoryKeyError(entity_id)

        # # Put entity in the cache.
        # if self._use_cache:
        #     self._cache[entity_id] = entity

        # Return entity.
        return entity

    def get_entity(self, entity_id, lt=None, lte=None):
        """
        Returns entity with given ID, optionally until position.
        """

        # Get a snapshot (None if none exist).
        if self._snapshot_strategy is not None:
            snapshot = self._snapshot_strategy.get_snapshot(entity_id, lt=lt, lte=lte)
        else:
            snapshot = None

        # Decide the initial state of the entity, and the
        # version of the last item applied to the entity.
        if snapshot is None:
            initial_state = None
            gt = None
        else:
            initial_state = entity_from_snapshot(snapshot)
            gt = snapshot.originator_version

        # Replay domain events.
        return self.replay_entity(entity_id, gt=gt, lt=lt, lte=lte, initial_state=initial_state)

    def replay_entity(self, entity_id, gt=None, gte=None, lt=None, lte=None, limit=None, initial_state=None,
                      query_descending=False):
        """
        Reconstitutes requested domain entity from domain events found in event store.
        """
        # Decide if query is in ascending order.
        #  - A "speed up" for when events are stored in descending order (e.g.
        #  in Cassandra) and it is faster to get them in that order.
        #  - This isn't useful when 'until' or 'after' or 'limit' are set,
        #    because the inclusiveness or exclusiveness of until and after
        #    and the end of the stream that is truncated by limit both depend on
        #    the direction of the query. Also paging backwards isn't useful, because
        #    all the events are needed eventually, so it would probably slow things
        #    down. Paging is intended to support replaying longer event streams, and
        #    only makes sense to work in ascending order.
        if gt is None and gte is None and lt is None and lte is None and self.__page_size__ is None:
            is_ascending = False
        else:
            is_ascending = not query_descending

        # Get entity's domain events from the event store.
        domain_events = self.event_store.get_domain_events(
            originator_id=entity_id,
            gt=gt,
            gte=gte,
            lt=lt,
            lte=lte,
            limit=limit,
            is_ascending=is_ascending,
            page_size=self.__page_size__
        )

        # The events will be replayed in ascending order.
        if not is_ascending:
            domain_events = list(reversed(list(domain_events)))

        # Replay the domain events, starting with the initial state.
        return self.replay_events(initial_state, domain_events)

    # Todo: This doesn't belong here. Perhaps Snapshotter that inherits from EventPlayer.
    def take_snapshot(self, entity_id, lt=None, lte=None):
        """
        Takes a snapshot of the entity as it existed after the most recent
        event, optionally less than, or less than or equal to, a particular position.
        """
        snapshot = None
        if self._snapshot_strategy:
            # Get the last event (optionally until a particular position).
            last_event = self.event_store.get_most_recent_event(entity_id, lt=lt, lte=lte)

            # If there is something to snapshot, then look for a snapshot
            # taken before or at the entity version of the last event. Please
            # note, the snapshot might have a smaller version number than
            # the last event if events occurred since the last snapshot was taken.
            if last_event is not None:
                last_snapshot = self._snapshot_strategy.get_snapshot(
                    entity_id, lt=lt, lte=lte
                )
                last_version = last_event.originator_version
                if last_snapshot and last_snapshot.originator_version == last_version:
                    # If up-to-date snapshot exists, there's nothing to do.
                    snapshot = last_snapshot
                else:
                    # Otherwise recover entity and take snapshot.
                    if last_snapshot:
                        initial_state = entity_from_snapshot(last_snapshot)
                        gt = last_snapshot.originator_version
                    else:
                        initial_state = None
                        gt = None
                    entity = self.replay_entity(entity_id, gt=gt, lte=last_version, initial_state=initial_state)
                    snapshot = self._snapshot_strategy.take_snapshot(entity_id, entity, last_version)

        return snapshot
