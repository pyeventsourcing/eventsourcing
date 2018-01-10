from abc import abstractmethod

from eventsourcing.infrastructure.activerecord import AbstractActiveRecordStrategy


class RelationalActiveRecordStrategy(AbstractActiveRecordStrategy):
    def append(self, sequenced_item_or_items):
        # Convert sequenced item(s) to active_record(s).
        if isinstance(sequenced_item_or_items, list):
            active_records = [self.to_active_record(i) for i in sequenced_item_or_items]
        else:
            active_records = [self.to_active_record(sequenced_item_or_items)]

        self._write_active_records(active_records, sequenced_item_or_items)

    def to_active_record(self, sequenced_item):
        """
        Returns an active record, from given sequenced item.
        """
        # Check we got a sequenced item.
        assert isinstance(sequenced_item, self.sequenced_item_class), (self.sequenced_item_class, type(sequenced_item))

        # Construct and return an ORM object.
        kwargs = self.get_field_kwargs(sequenced_item)
        return self.active_record_class(**kwargs)

    @abstractmethod
    def _write_active_records(self, active_records, sequenced_items):
        """
        Actually creates records in the database.
        """
