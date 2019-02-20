from __future__ import absolute_import, division, print_function, unicode_literals

import json
from abc import ABC, abstractmethod

import requests

from eventsourcing.domain.model.array import BigArray
from eventsourcing.infrastructure.base import ACIDRecordManager
from eventsourcing.utils.transcoding import ObjectJSONDecoder, ObjectJSONEncoder, json_dumps

DEFAULT_SECTION_SIZE = 20


class Section(object):
    """
    Section of a notification log.

    Contains items, and has an ID.

    May also have either IDs of previous and next sections of the notification log.
    """

    def __init__(self, section_id, items, previous_id=None, next_id=None):
        self.section_id = section_id
        self.items = items
        self.previous_id = previous_id
        self.next_id = next_id


class AbstractNotificationLog(ABC):
    """
    Presents a sequence of sections from a sequence of notifications.
    """

    @abstractmethod
    def __getitem__(self, section_id):
        """
        Get section of notification log.

        :rtype: Section
        """


class LocalNotificationLog(AbstractNotificationLog):
    """
    Presents a sequence of sections from a sequence of notifications.
    """

    def __init__(self, section_size=None):
        self.section_size = section_size or DEFAULT_SECTION_SIZE
        # self.last_start = None

    def __getitem__(self, section_id):
        # Get section of notification log.
        next_position = None
        if section_id == 'current':

            # Get start of the last section.
            next_position = self.get_next_position()
            start = next_position // self.section_size * self.section_size
        else:

            try:
                first_item_number, last_item_number = section_id.split(',')
            except ValueError as e:
                raise ValueError("Couldn't split '{}': {}".format(section_id, e))

            # Convert from 1-based to 0-based.
            start = int(first_item_number) - 1

            # Go back to nearest section start.
            start = start // self.section_size * self.section_size

        # Get stop index (section doesn't include this one).
        stop = start + self.section_size

        # Get the items.
        items = list(self.get_items(start, stop, next_position))

        # Get previous and next section IDs.
        if start:
            first_item_number = start + 1 - self.section_size
            last_item_number = first_item_number - 1 + self.section_size
            previous_id = self.format_section_id(first_item_number, last_item_number)
        else:
            previous_id = None

        if len(items) == self.section_size:
            first_item_number = start + 1 + self.section_size
            last_item_number = first_item_number - 1 + self.section_size
            next_id = self.format_section_id(first_item_number, last_item_number)
        else:
            next_id = None

        # Return a section of the notification log.
        section_id = self.format_section_id(start + 1, start + self.section_size)
        return Section(
            section_id=section_id,
            items=items,
            previous_id=previous_id,
            next_id=next_id,
        )

    @abstractmethod
    def get_next_position(self):
        """
        Returns items for section.

        :rtype: int
        """

    @abstractmethod
    def get_items(self, start, stop, next_position=None):
        """
        Returns items for section.

        :rtype: list
        """

    @staticmethod
    def format_section_id(first_item_number, last_item_number):
        return '{},{}'.format(first_item_number, last_item_number)


class RecordManagerNotificationLog(LocalNotificationLog):
    def __init__(self, record_manager, section_size):
        super(RecordManagerNotificationLog, self).__init__(section_size)
        assert isinstance(record_manager, ACIDRecordManager), record_manager
        assert record_manager.contiguous_record_ids
        self.record_manager = record_manager

    def get_items(self, start, stop, next_position=None):
        notifications = []
        for record in self.record_manager.get_notifications(start, stop):
            notification = {
                'id': getattr(record, self.record_manager.notification_id_name)
            }
            for field_name in self.record_manager.field_names:
                notification[field_name] = getattr(record, field_name)
            if hasattr(record, 'causal_dependencies'):
                notification['causal_dependencies'] = record.causal_dependencies
            notifications.append(notification)
        return notifications

    def get_next_position(self):
        """Next unoccupied position in zero-based sequence.

        Since the notification IDs are one-based, the next position is
        the current max notification ID. If there are no records,
        the max notification ID will be None, and the next position is zero.
        """
        return self.record_manager.get_max_record_id() or 0


class BigArrayNotificationLog(LocalNotificationLog):
    def __init__(self, big_array, section_size):
        super(BigArrayNotificationLog, self).__init__(section_size)
        assert isinstance(big_array, BigArray)
        if big_array.repo.array_size % section_size:
            raise ValueError("Section size {} doesn't divide array size {}".format(
                section_size, big_array.repo.array_size
            ))
        self.big_array = big_array

    def get_items(self, start, stop, next_position=None):
        next_position = self.get_next_position() if next_position is None else next_position
        stop = min(stop, next_position)
        return self.big_array[start:stop]

    def get_next_position(self):
        return self.big_array.get_next_position()


class RemoteNotificationLog(AbstractNotificationLog):
    def __init__(self, base_url, json_decoder_class=None):
        self.base_url = base_url
        self.json_decoder_class = json_decoder_class

    def __getitem__(self, section_id):
        section_json = self.get_json(section_id)
        return self.deserialize_section(section_json)

    def deserialize_section(self, section_json):
        try:
            decoder_class = self.json_decoder_class or ObjectJSONDecoder
            section = Section(**json.loads(section_json, cls=decoder_class))
        except ValueError as e:
            raise ValueError("Couldn't deserialize notification log section: "
                             "{}: {}".format(e, section_json))
        return section

    def get_json(self, section_id):
        notification_log_url = self.make_notification_log_url(section_id)
        return self.get_resource(notification_log_url)

    def get_resource(self, doc_url):
        representation = requests.get(doc_url).content
        if isinstance(representation, type(b'')):
            representation = representation.decode('utf8')
        return representation

    def make_notification_log_url(self, section_id):
        return '{}/{}/'.format(self.base_url.strip('/'), section_id)


class NotificationLogReader(ABC):
    def __init__(self, notification_log, use_direct_query_if_available=False):
        assert isinstance(notification_log, AbstractNotificationLog)
        self.notification_log = notification_log
        self.section_count = 0
        self.position = 0
        self.use_direct_query_if_available = use_direct_query_if_available

    def __getitem__(self, item=None):
        if isinstance(item, slice):
            assert item.start >= 0, item.start
            self.seek(item.start)
            return self.read_items(item.stop)
        else:
            assert isinstance(item, int), type(item)
            assert item >= 0, item
            self.seek(item)
            return self.read_list(advance_by=1)[0]

    def __iter__(self):
        return self.read_items()

    def __next__(self):
        try:
            return self.read_list(advance_by=1)[0]
        except IndexError:
            raise StopIteration

    def seek(self, position):
        if position < 0:
            raise ValueError("Position less than zero: {}".format(position))
        self.position = position

    def read(self, advance_by=None):
        return self.read_items(advance_by=advance_by)

    def read_items(self, stop_index=None, advance_by=None):
        self.section_count = 0

        start_item_num = self.position + 1

        # Validate the position.
        if self.position < 0:
            raise ValueError("Position less than zero: {}".format(self.position))

        if self.use_direct_query_if_available and isinstance(
                self.notification_log, RecordManagerNotificationLog):
            if advance_by is not None:
                stop_item_num = start_item_num + advance_by
            else:
                stop_item_num = None
            # Directly query for notifications.
            for item in self.notification_log.get_items(start_item_num - 1, stop_item_num):
                yield item
                self.position += 1

        else:
            # Otherwise, use sections (Vaughn Vernon's linked section design).
            section = self.notification_log['current']

            # Follow previous links.
            while section.previous_id:

                # Break if we can go forward from here.
                if start_item_num is not None:
                    if int(section.section_id.split(',')[0]) <= start_item_num:
                        break

                # Get the previous document.
                section_id = section.previous_id
                section = self.notification_log[section_id]

            # Yield items in first section, optionally after last item number.
            self.section_count += 1
            items = section.items
            if start_item_num is not None:
                section_start_num = int(section.section_id.split(',')[0])
                from_index = start_item_num - section_start_num
                items = items[from_index:]

            if advance_by is None:
                advance_by = -1

            # Yield all items in all subsequent sections.
            while True:

                items_iter = iter(items)
                while True:
                    if stop_index is not None and self.position >= stop_index:
                        return
                    if advance_by == 0:
                        return
                    try:
                        item = next(items_iter)
                    except StopIteration:
                        break
                    self.position += 1
                    advance_by -= 1
                    yield item

                if section.next_id:
                    # Follow link to get next section.
                    section = self.notification_log[section.next_id]
                    items = section.items
                    self.section_count += 1
                else:
                    break

    def read_list(self, advance_by=None):
        return list(self.read_items(advance_by=advance_by))


class NotificationLogView(object):
    def __init__(self, notification_log, json_encoder_class=None):
        assert isinstance(notification_log, LocalNotificationLog), type(notification_log)
        self.notification_log = notification_log
        self.json_encoder_class = json_encoder_class or ObjectJSONEncoder

    def present_section(self, section_id):
        section = self.notification_log[section_id]
        is_archived = bool(section.next_id)
        section_json = json_dumps(section.__dict__, self.json_encoder_class)
        return section_json, is_archived
