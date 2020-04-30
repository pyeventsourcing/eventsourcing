from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Union

from eventsourcing.domain.model.array import BigArray
from eventsourcing.infrastructure.base import (
    AbstractRecordManager,
    RecordManagerWithNotifications,
)

DEFAULT_SECTION_SIZE = 20


class Section(object):
    """
    Section of a notification log.

    Contains items, and has an ID.

    May also have either IDs of previous and next sections of the notification log.
    """

    def __init__(
        self,
        section_id: str,
        items: List,
        previous_id: Optional[str] = None,
        next_id: Optional[str] = None,
    ):
        self.section_id = section_id
        self.items = items
        self.previous_id = previous_id
        self.next_id = next_id


class AbstractNotificationLog(ABC):
    """
    Presents a sequence of sections from a sequence of notifications.
    """

    @abstractmethod
    def __getitem__(self, section_id: str) -> Section:
        """
        Get section of notification log.

        :param section_id: ID of a section of the notification log.
        """

    @property
    @abstractmethod
    def section_size(self) -> int:
        """
        Size of section of notification log.
        """


class LocalNotificationLog(AbstractNotificationLog):
    """
    Presents a sequence of sections from a sequence of notifications.
    """

    def __init__(self, section_size: Optional[int] = None):
        self._section_size: int = section_size or DEFAULT_SECTION_SIZE
        # self.last_start = None

    @property
    def section_size(self) -> int:
        """
        Size of section of notification log.
        """
        return self._section_size

    def __getitem__(self, section_id: str) -> Section:
        # Get section of notification log.
        if section_id == "current":

            # Get start of the last section.
            next_position = self.get_next_position()
            start: int = next_position // self.section_size * self.section_size
        else:

            try:
                section_id_part1, _ = section_id.split(",")
            except ValueError as e:
                raise ValueError("Couldn't split '{}': {}".format(section_id, e))

            # Convert from 1-based to 0-based.
            start = int(section_id_part1) - 1

            # Go back to nearest section start.
            start = start // self.section_size * self.section_size

        # Get stop index (section doesn't include this one).
        stop = start + self.section_size

        # Get the items.
        items = list(self.get_items(start, stop))

        # Get previous and next section IDs.
        previous_id: Optional[str] = None
        next_id: Optional[str] = None
        if start:
            first_item_number = start + 1 - self.section_size
            last_item_number = first_item_number - 1 + self.section_size
            previous_id = self.format_section_id(first_item_number, last_item_number)

        if len(items) == self.section_size:
            first_item_number = start + 1 + self.section_size
            last_item_number = first_item_number - 1 + self.section_size
            next_id = self.format_section_id(first_item_number, last_item_number)

        # Return a section of the notification log.
        section_id = self.format_section_id(start + 1, start + self.section_size)
        return Section(
            section_id=section_id, items=items, previous_id=previous_id, next_id=next_id
        )

    @abstractmethod
    def get_next_position(self) -> int:
        """Returns next unoccupied position in zero-based sequence.

        Since the notification IDs are one-based, the next position
        in the zero-based sequence equals the current max notification ID
        which is 1-based. If there are no records, the max notification ID
        will be None, and the next position is zero.

        :returns: Non-negative integer.
        :rtype: int
        """

    @abstractmethod
    def get_items(self, start: int, stop: int) -> Sequence[Any]:
        """
        Returns items for section.
        """

    @staticmethod
    def format_section_id(first_item_number: int, last_item_number: int) -> str:
        return "{},{}".format(first_item_number, last_item_number)


class RecordManagerNotificationLog(LocalNotificationLog):
    """
    Local notification log that gets notifications from a record manager.
    """

    def __init__(
        self, record_manager: AbstractRecordManager, section_size: Optional[int] = None
    ):
        super(RecordManagerNotificationLog, self).__init__(section_size=section_size)
        assert isinstance(
            record_manager, RecordManagerWithNotifications
        ), record_manager
        assert record_manager.contiguous_record_ids
        self.record_manager = record_manager

    def get_items(self, start: int, stop: Optional[int]) -> Sequence[Any]:
        """
        Returns notification in log.

        :param start: Inclusive start position in log.
        :param stop: Inclusive stop position in log.
        :return:
        """
        return list(self.record_manager.get_notifications(start, stop))

    def get_next_position(self) -> int:
        """Returns next unoccupied position in zero-based sequence.

        Since the notification IDs are one-based, the next position
        in the zero-based sequence equals the current max notification ID
        which is 1-based. If there are no records, the max notification ID
        will be None, and the next position is zero.

        :returns: Non-negative integer.
        :rtype: int
        """
        return self.record_manager.get_max_notification_id()


class BigArrayNotificationLog(LocalNotificationLog):
    """
    Notification log that uses the BigArray class.
    """

    def __init__(self, big_array: BigArray, section_size: int):
        super(BigArrayNotificationLog, self).__init__(section_size)
        assert isinstance(big_array, BigArray)
        if big_array.repo.array_size % section_size:
            raise ValueError(
                "Section size {} doesn't divide array size {}".format(
                    section_size, big_array.repo.array_size
                )
            )
        self.big_array = big_array

    def get_items(self, start: int, stop: int) -> Sequence[Any]:
        next_position = self.get_next_position()
        stop = min(stop, next_position)
        return self.big_array[start:stop]

    def get_next_position(self) -> int:
        """Returns next unoccupied position in zero-based sequence.

        :returns: Non-negative integer.
        :rtype: int
        """
        return self.big_array.get_next_position()


class NotificationLogReader(ABC):
    def __init__(
        self,
        notification_log: AbstractNotificationLog,
        use_direct_query_if_available: bool = False,
    ):
        self.notification_log = notification_log
        self.section_count = 0
        self.use_direct_query_if_available = use_direct_query_if_available
        self.position = 0
        self.seek(0)

    def __getitem__(self, item: Union[int, slice]) -> Iterable:
        if isinstance(item, slice):
            assert item.start >= 0, item.start
            self.seek(item.start)
            return self.iter_notifications(stop_index=item.stop)
        else:
            assert isinstance(item, int), type(item)
            assert item >= 0, item
            self.seek(item)
            return self.list_notifications(advance_by=1)[0]

    def __iter__(self) -> Iterable:
        return self.iter_notifications()

    def __next__(self) -> Dict[str, Any]:
        try:
            return self.list_notifications(advance_by=1)[0]
        except IndexError:
            raise StopIteration

    def seek(self, position: int) -> None:
        """
        Sets position of reader in notification log sequence.

        This represents the position of the last notification read by the reader.
        The next notification returned by the reader will be the next position.

        :param int position: Position is notification log sequence.
        :raises ValueError: if the position is less than zero
        """
        if position < 0:
            raise ValueError("Position less than zero: {}".format(position))
        self.position = position

    def read(self, advance_by: Optional[int] = None) -> Iterator[Dict[str, Any]]:
        return self.iter_notifications(advance_by=advance_by)

    def list_notifications(
        self, advance_by: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        return list(self.iter_notifications(advance_by=advance_by))

    def iter_notifications(
        self, stop_index: Optional[int] = None, advance_by: Optional[int] = None
    ) -> Iterator[Dict[str, Any]]:
        self.section_count = 0

        # Validate the position.
        if self.position < 0:
            raise ValueError("Position less than zero: {}".format(self.position))

        if self.use_direct_query_if_available and isinstance(
            self.notification_log, RecordManagerNotificationLog
        ):
            # Directly query for notifications. The args 'start' and 'stop'
            # are the start and stop positions for a slice in a zero-based
            # index. The stop position will not be included in the results
            # obtained from notification_log.get_items(start, stop), much
            # like a Python slice used to get items from a Python list.

            start = self.position
            if advance_by is not None:
                stop: Optional[int] = start + advance_by
            elif stop_index:
                stop = stop_index
            else:
                stop = None

            for item in self.notification_log.get_items(start=start, stop=stop):
                yield item
                self.position += 1

        else:
            # Otherwise, use sections (Vaughn Vernon's linked section design).
            section = self.notification_log[self.initial_section_id]

            # We need to create a section ID, which uses notification
            # numbers, and they start from 1. The position int points to next unread
            # position in notification log, using a zero-based integer sequence to
            # index an array of notifications. The number of the notification is
            # always one greater than the index of its position.
            start_item_num = self.position + 1

            # Follow previous links.
            while section.previous_id:

                # Break if we can go forward from here.
                if int(section.section_id.split(",")[0]) <= start_item_num:
                    break

                # Get the previous document.
                section_id = section.previous_id
                section = self.notification_log[section_id]

            # Yield items in first section, optionally after last item number.
            self.section_count += 1
            items = section.items
            if start_item_num is not None:
                section_start_num = int(section.section_id.split(",")[0])
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

    @property
    def initial_section_id(self) -> str:
        """
        Returns initial section ID used to start getting
        linked sections from the notification log.

        Slight departure from Vaughn Vernon's design by not using 'current'
        as initial section ID, but a section ID that just includes the
        "next" position, which the notification log can use to return
        the section containing this position. This avoids lengthy back-
        tracking when reader has a lot of notifications to catch-up on.

        This property has been extracted in order to allow a subclass to
        adjust this default behaviour.

        It would be possible to calculate the actual section ID from the
        current reader position. Using section ID of an actual section
        may hit a cache and avoid troubling the server, but the reader
        would need to know the section size of the notification log it
        is reading. If we don't know section size, perhaps it is a remote
        notification log, we can use 'current' to hit a cache. In future, it
        might be possible to ask the notification log to disclose it's section
        size, or compute an actual section ID for a given position.

        :return: A notification log section ID.
        :rtype: str
        """
        # Calculate the section start and end.
        #  - notification ID sequence start,end are 1-based
        #  - 'position' is 1-based, but 1 behind the next position
        #  - we want to get the next position
        #  - the modulo calculation works with 0-based index
        #  - 'position' is equal to zero-based index of next item
        #  - section IDs use 1-based start and end values.
        section_size = self.notification_log.section_size
        start = self.position // section_size * section_size
        end = start + section_size
        return "%d,%d" % (start + 1, end)

    def read_list(self, advance_by: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Deprecated in 8.0.0.

        Please use list_notifications() instead.
        """
        return self.list_notifications(advance_by=advance_by)

    def read_items(
        self, stop_index: Optional[int] = None, advance_by: Optional[int] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Deprecated in 8.0.0.

        Please use iter_notifications() instead.
        """
        return self.iter_notifications(stop_index=stop_index, advance_by=advance_by)
