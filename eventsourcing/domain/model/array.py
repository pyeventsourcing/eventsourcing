from abc import abstractproperty
from math import ceil, log
from uuid import uuid5

import six

from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.entity import AbstractEntityRepository, TimestampedVersionedEntity
from eventsourcing.domain.model.events import publish
from eventsourcing.exceptions import ConcurrencyError, SequenceFullError


class PositionTaken(TimestampedVersionedEntity.Event):
    """Occurs when an item is set at a position in an array."""


class Array(object):
    def __init__(self, array_id, repo, meta=None):
        assert isinstance(repo, AbstractArrayRepository)
        self.id = array_id
        self.repo = repo

    @retry(ConcurrencyError, max_retries=50, wait=0.01)
    def append(self, item):
        """Sets item in next position after the last item."""
        next_position = self.__len__()
        self.__setitem__(next_position, item)

    def __setitem__(self, position, item):
        """
        Sets item in array, at given position.
        
        Won't overrun the end of the sequence, because the position is
        fixed to be less than the max_size, won't overwrite due to OCC.

        Publishes an ItemAppended event.
        """
        position = position if position is not None else self.__len__()
        size = self.repo.array_size
        if size and position >= size:
            raise SequenceFullError
        event = PositionTaken(
            originator_id=self.id,
            originator_version=position,
            item=item,
        )
        publish(event)

    def __getitem__(self, item):
        """
        Returns item at index or, items in slice.
        """
        assert isinstance(item, (six.integer_types, slice))
        array_len = None
        if isinstance(item, six.integer_types):
            if item < 0:
                if array_len is None:
                    array_len = self.__len__()
                index = array_len + item
                if index < 0:
                    raise IndexError("Sequence index out of range: {}".format(item))
            else:
                index = item
            event = self.repo.event_store.get_domain_event(originator_id=self.id, eq=index)
            return event.item
        elif isinstance(item, slice):
            assert item.step in (None, 1), "Slice step must be 1: {}".format(str(item.step))
            if item.start is None:
                start_index = 0
            elif item.start < 0:
                array_len = self.__len__()
                start_index = max(array_len + item.start, 0)
            else:
                start_index = item.start

            if not isinstance(item.stop, six.integer_types):
                limit = None
            elif item.stop < 0:
                if array_len is None:
                    array_len = self.__len__()
                limit = array_len + item.stop - start_index
            else:
                limit = item.stop - start_index

            if limit is not None and limit <= 0:
                return []

            events = self.repo.event_store.get_domain_events(originator_id=self.id,
                                                             gte=start_index, limit=limit)
            items = [e.item for e in events]
            return items

    def __len__(self):
        """
        Returns length of array.
        """
        return self.get_last_and_len()[1]

    def get_last_and_len(self):
        events = self.repo.event_store.get_domain_events(
            originator_id=self.id,
            limit=1,
            is_ascending=False,
        )
        if len(events):
            event = events[0]
            return event.item, event.originator_version + 1
        else:
            return None, 0

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.id == other.id


class BigArray(Array):
    def __init__(self, array_id, repo, subrepo):
        assert isinstance(repo, AbstractBigArrayRepository)
        assert isinstance(subrepo, AbstractArrayRepository)
        super(BigArray, self).__init__(array_id=array_id, repo=repo)
        self.subrepo = subrepo

    def get_last_array(self):
        """
        Returns last array in compound.

        :rtype: CompoundSequenceReader
        """
        # Get the root array (might not have been registered).
        root = self.subrepo[self.id]

        # Get length and last item in the root array.
        apex_id, apex_height = root.get_last_and_len()

        # Bail if there isn't anything yet.
        if apex_id is None:
            return None, None

        # Get the current apex array.
        apex = self.subrepo[apex_id]
        assert isinstance(apex, Array)

        # Descend until hitting the bottom.
        array = apex
        array_i = 0
        height = apex_height
        while height > 1:
            height -= 1
            array_id, width = array.get_last_and_len()
            assert width > 0
            offset = width - 1
            array_i += offset * self.subrepo.array_size ** height
            array = self.subrepo[array_id]

        return array, array_i

    def create_array_id(self, i, j):
        return uuid5(self.id, str((i, j)))

    def get_last_and_len(self):
        sequence, i = self.get_last_array()
        if sequence is None:
            return None, 0
        item, n = sequence.get_last_and_len()
        return item, i + n

    def calc_parent_i_j_h_p(self, i, j, h):
        """
        Returns get_big_array and end of span of parent sequence that contains given child.
        """
        N = self.subrepo.array_size
        c_i = i
        c_j = j
        c_h = h
        # Calculate the number of the sequence in its row (sequences
        # with same height), from left to right, starting from 0.
        c_n = c_i // (N ** c_h)
        p_n = c_n // N
        # Position of the child ID in the parent array.
        p_p = c_n % N
        # Parent height is child height plus one.
        p_h = c_h + 1
        # Span of sequences in parent row is max size N, to the power of the height.
        span = N ** p_h
        # Calculate parent i and j.
        p_i = p_n * span
        p_j = p_i + span
        # Check the parent i,j bounds the child i,j, ie child span is contained by parent span.
        assert p_i <= c_i, 'i greater on parent than child: {}'.format(p_i, p_j)
        assert p_j >= c_j, 'j less on parent than child: {}'.format(p_i, p_j)
        # Return parent i, j, h, p.
        return p_i, p_j, p_h, p_p

    def __getitem__(self, item):
        assert isinstance(item, (six.integer_types, slice))
        # Calculate the i and j of the containing base sequence.
        if isinstance(item, six.integer_types):
            if item >= 0:
                return self.get_item(item)
            else:
                last, length = self.get_last_and_len()
                if item == -1:
                    return last
                else:
                    item = length + item
                    return self.get_item(item)
        elif isinstance(item, slice):
            return self.get_slice(item)

    def get_item(self, item):
        size = self.subrepo.array_size
        n = item // size
        i = n * size
        j = i + size
        offset = item - i
        array_id = self.create_array_id(i, j)
        sequence = self.subrepo[array_id]
        return sequence[offset]

    def get_slice(self, item):
        assert isinstance(item, slice)
        assert item.step in (None, 1), "Slice step must be 1: {}".format(str(item.step))

        array_len = None

        if item.start is None:
            start = 0
        elif item.start < 0:
            array_len = self.__len__()
            start = max(array_len + item.start, 0)
        else:
            start = item.start

        if not isinstance(item.stop, six.integer_types):
            if array_len is None:
                array_len = self.__len__()
            stop = array_len
        elif item.stop < 0:
            if array_len is None:
                array_len = self.__len__()
            stop = array_len + item.stop
        else:
            stop = item.stop

        if stop <= start:
            return

        size = self.subrepo.array_size
        while True:
            n = start // size
            i = n * size
            j = i + size
            substart = start - i
            substop = stop - i
            array_id = self.create_array_id(i, j)
            sequence = self.subrepo[array_id]
            for item in sequence[substart:substop]:
                yield item
            start = j
            if start > stop:
                break

    def __setitem__(self, position, item):
        # Calculate the base array i.
        size = self.subrepo.array_size
        i = (position // size) * size
        j = i + size

        # Calculate the height of the apex of the compound that would contain n.
        required_height = self.calc_required_height(position, size)
        assert required_height > 0

        # Set the item in the base array.
        array_id = self.create_array_id(i, j)
        array = self.subrepo[array_id]
        array[position - i] = item

        # Set array IDs in containing arrays,
        # up to the required height.
        h = 1
        while h < required_height:
            child_id = array_id
            # Calculate i and j for parent (start and stop positions),
            # and height of parent, and position of child in parent.
            i, j, h, p = self.calc_parent_i_j_h_p(i, j, h)
            array_id = self.create_array_id(i, j)
            array = self.subrepo[array_id]
            try:
                array[p] = child_id
            except ConcurrencyError:
                return

        # Set the apex to the root array.
        assert array_id
        root = self.subrepo[self.id]
        try:
            root[required_height - 1] = array_id
        except ConcurrencyError:
            return

    def calc_required_height(self, n, size):
        if size <= 0:
            raise ValueError("Size must be greater than 0")
        capacity = size ** size
        if n + 1 > capacity:
            raise IndexError
        if n == 0 or n == 1:
            return 1
        return int(ceil(log(max(size, n + 1), size)))


class AbstractArrayRepository(AbstractEntityRepository):
    """
    Repository for sequence objects.
    """

    def __init__(self, array_size=10000, *args, **kwargs):
        super(AbstractArrayRepository, self).__init__(*args, **kwargs)
        self.array_size = array_size


class AbstractBigArrayRepository(AbstractArrayRepository):
    """
    Repository for compound sequence objects.
    """

    @abstractproperty
    def subrepo(self):
        """Sub-sequence repository."""
