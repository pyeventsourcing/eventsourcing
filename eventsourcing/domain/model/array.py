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
        position = len(self)
        self[position] = item

    def __setitem__(self, position, item):
        """
        Appends item to sequence, by publishing an ItemAppended event.

        Won't overrun the end of the sequence, because the position is
        fixed to be less than the max_size, won't overwrite due to OCC.
        """
        position = position if position is not None else len(self)
        size = self.repo.array_size
        if size and position >= size:
            raise SequenceFullError
        event = PositionTaken(
            originator_id=self.id,
            originator_version=position,
            item=item,
        )
        publish(event)

    def get_next_position(self):
        last_event = self.repo.event_store.get_most_recent_event(self.id)
        if last_event is None:
            return 0
        else:
            return last_event.originator_version + 1

    def __getitem__(self, item):
        assert isinstance(item, (six.integer_types, slice))
        sequence_len = None
        if isinstance(item, six.integer_types):
            if item < 0:
                if sequence_len is None:
                    sequence_len = len(self)
                index = sequence_len + item
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
                sequence_len = len(self)
                start_index = max(sequence_len + item.start, 0)
            else:
                start_index = item.start

            if not isinstance(item.stop, six.integer_types):
                limit = None
            elif item.stop < 0:
                if sequence_len is None:
                    sequence_len = len(self)
                limit = sequence_len + item.stop - start_index
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

    def __repr__(self):
        return "{}(id={})".format(type(self).__name__, self.id)

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.id == other.id

    def get_last(self):
        return self.get_last_and_len()[0]

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
        sequence_i = 0
        height = apex_height
        while height > 1:
            height -= 1
            sequence_id, width = array.get_last_and_len()
            assert width > 0
            offset = width - 1
            sequence_i += offset * self.subrepo.array_size ** height
            array = self.subrepo[sequence_id]

        return array, sequence_i

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
        sequence_id = self.create_array_id(i, j)
        sequence = self.subrepo[sequence_id]
        return sequence[offset]

    def get_slice(self, item):
        assert item.step in (None, 1), "Slice step must be 1: {}".format(str(item.step))

        sequence_len = None

        if item.start is None:
            start = 0
        elif item.start < 0:
            sequence_len = len(self)
            start = max(sequence_len + item.start, 0)
        else:
            start = item.start

        if not isinstance(item.stop, six.integer_types):
            if sequence_len is None:
                sequence_len = len(self)
            stop = sequence_len
        elif item.stop < 0:
            if sequence_len is None:
                sequence_len = len(self)
            stop = sequence_len + item.stop
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
            sequence_id = self.create_array_id(i, j)
            sequence = self.subrepo[sequence_id]
            for item in sequence[substart:substop]:
                yield item
            start = j
            if start > stop:
                break

    def __setitem__(self, position, item):
        # Calculate the base array i.
        size = self.subrepo.array_size
        i = position // size * size
        j = i + size

        # Calculate the height of the apex of the compound that would contain n.
        required_height = self.calc_required_height(position, size)
        assert required_height > 0

        array_id = self.create_array_id(i, j)
        array = self.subrepo[array_id]
        array[position - i] = item

        h = 1
        while h < required_height:
            child_id = array_id
            i, j, h, p = self.calc_parent_i_j_h_p(i, j, h)
            array_id = self.create_array_id(i, j)
            array = self.subrepo[array_id]
            try:
                array[p] = child_id
            except ConcurrencyError:
                return

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
