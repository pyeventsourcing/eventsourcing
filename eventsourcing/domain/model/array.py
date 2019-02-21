from abc import abstractproperty
from math import ceil, log
from uuid import uuid5

from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.entity import AbstractEntityRepository, TimestampedVersionedEntity
from eventsourcing.domain.model.events import publish
from eventsourcing.exceptions import ArrayIndexError, ConcurrencyError


class ItemAssigned(TimestampedVersionedEntity.Event):
    """Occurs when an item is set at a position in an array."""

    def __init__(self, item, index, *args, **kwargs):
        kwargs['item'] = item
        super(ItemAssigned, self).__init__(originator_version=index, *args, **kwargs)

    @property
    def item(self):
        return self.__dict__['item']

    @property
    def index(self):
        return self.originator_version


class Array(object):
    def __init__(self, array_id, repo):
        assert isinstance(repo, AbstractArrayRepository)
        self.id = array_id
        self.repo = repo

    @retry(ConcurrencyError, max_attempts=50, wait=0.01)
    def append(self, item):
        """Sets item in next position after the last item."""
        self.__setitem__(self.get_next_position(), item)

    def __setitem__(self, index, item):
        """
        Sets item in array, at given index.

        Won't overrun the end of the array, because
        the position is fixed to be less than base_size.
        """
        size = self.repo.array_size
        if size and index >= size:
            raise ArrayIndexError("Index is {}, but size is {}".format(index, size))
        event = ItemAssigned(
            originator_id=self.id,
            index=index,
            item=item,
        )
        publish(event)

    def __getitem__(self, item):
        """
        Returns item at index, or items in slice.
        """
        assert isinstance(item, (int, slice))
        array_size = self.repo.array_size
        if isinstance(item, int):
            if item < 0:
                index = array_size + item
                if index < 0:
                    raise ArrayIndexError("Array index out of range: {}".format(item))
            else:
                index = item
            event = self.get_item_assigned(index)
            assert isinstance(event, ItemAssigned)
            return event.item
        elif isinstance(item, slice):
            assert item.step in (None, 1), "Slice stepping not supported, yet"
            if item.start is None:
                start_index = 0
            elif item.start < 0:
                start_index = max(array_size + item.start, 0)
            else:
                start_index = item.start

            if not isinstance(item.stop, int):
                stop_index = array_size
            elif item.stop < 0:
                stop_index = array_size + item.stop
            else:
                stop_index = item.stop

            if stop_index is not None:
                if stop_index <= 0:
                    return []
                # Avoid passing massive integers into the database.
                if array_size is not None:
                    stop_index = min(stop_index, self.repo.array_size)

            items_assigned = self.get_items_assigned(stop_index=stop_index, start_index=start_index)
            items_dict = {str(i.originator_version): i.item for i in items_assigned}
            items = [items_dict.get(str(i)) for i in range(start_index, stop_index)]
            return items

    def __len__(self):
        """
        Returns length of array.
        """
        return self.repo.array_size

    def get_next_position(self):
        return self.get_last_item_and_next_position()[1]

    def get_last_item_and_next_position(self):
        items_assigned = self.get_items_assigned(limit=1, is_ascending=False)
        if len(items_assigned) == 0:
            return None, 0
        item_assigned = items_assigned[0]
        return item_assigned.item, item_assigned.index + 1

    def get_items_assigned(self, start_index=None, stop_index=None, limit=None, is_ascending=True):
        return self.repo.event_store.get_domain_events(
            originator_id=self.id,
            gte=start_index,
            lt=stop_index,
            limit=limit,
            is_ascending=is_ascending,
        )

    def get_item_assigned(self, index):
        try:
            item_assigned = self.repo.event_store.get_domain_event(
                originator_id=self.id,
                position=index,
            )
        except IndexError as e:
            raise ArrayIndexError(e)
        else:
            return item_assigned

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.id == other.id

    def __ne__(self, other):
        return not self.__eq__(other)


class BigArray(Array):
    """
    A virtual array holding items in indexed
    positions, across a number of Array instances.

    Getting and setting items at index position is
    supported. Slices are supported, and operate
    across the underlying arrays. Appending is also
    supported.

    BigArray is designed to overcome the concern of
    needing a single large sequence that may not be
    suitably stored in any single partiton. In simple
    terms, if events of an aggregate can fit in a
    partition, we can use the same size partition
    to make a tree of arrays that will certainly
    be capable of sequencing all the events of the
    application in a single stream.

    With normal size base arrays, enterprise applications
    can expect read and write time to be approximately
    constant with respect to the number of items in the array.

    The array is composed of a tree of arrays,
    which gives the capacity equal to the size
    of each array to the power of the size of
    each array. If the arrays are limited to be
    about the maximum size of an aggregate event
    stream (a large number but not too many that
    would cause there to be too much data in any
    one partition, let's say 1000s to be safe)
    then it would be possible to fit such a large
    number of aggregates in the corresponding
    BigArray, that we can be confident it would
    be full.

    Write access time in the worst case, and the time
    to identify the index of the last item in the big
    array, is proportional to the log of the highest
    assigned index to base the underlying array
    size. Write time on average, and read time given an
    index, is constant with respect to the number of items
    in a BigArray.

    Items can be appended in log time in a single thread.
    However, the time between reading the current last index
    and claiming the next position leads to contention and
    retries when there are lots of threads of execution all
    attempting to append items, which inherently limits throughput.

    Todo: Not possible in Cassandra, but maybe do it in a
    transaction in SQLAlchemy?

    An alternative to reading the last item before writing
    the next is to use an integer sequence generator to
    generate a stream of integers. Items can be assigned
    to index positions in a big array, according to the integers
    that are issued. Throughput will then be much better, and
    will be limited only by the rate at which the database can have
    events written to it (unless the number generator is quite slow).

    An external integer sequence generator, such as Redis' INCR
    command, or an auto-incrementing database column, may
    constitute a single point of failure.

    """

    def __init__(self, array_id, repo):
        assert isinstance(repo, AbstractArrayRepository), type(repo)
        super(BigArray, self).__init__(array_id=array_id, repo=repo)

    def get_last_array(self):
        """
        Returns last array in compound.

        :rtype: CompoundSequenceReader
        """
        # Get the root array (might not have been registered).
        root = self.repo[self.id]

        # Get length and last item in the root array.
        apex_id, apex_height = root.get_last_item_and_next_position()

        # Bail if there isn't anything yet.
        if apex_id is None:
            return None, None

        # Get the current apex array.
        apex = self.repo[apex_id]
        assert isinstance(apex, Array)

        # Descend until hitting the bottom.
        array = apex
        array_i = 0
        height = apex_height
        while height > 1:
            height -= 1
            array_id, width = array.get_last_item_and_next_position()
            assert width > 0
            offset = width - 1
            array_i += offset * self.repo.array_size ** height
            array = self.repo[array_id]

        return array, array_i

    def get_last_item_and_next_position(self):
        sequence, i = self.get_last_array()
        if sequence is None:
            return None, 0
        item, n = sequence.get_last_item_and_next_position()
        return item, i + n

    def __getitem__(self, item):
        assert isinstance(item, (int, slice))
        # Calculate the i and j of the containing base sequence.
        if isinstance(item, int):
            return self.get_item(item)
        elif isinstance(item, slice):
            assert item.step in (None, 1), "Slice step must be 1: {}".format(str(item.step))
            return self.get_slice(item.start, item.stop)

    def get_item(self, position):
        if position < 0:
            last, length = self.get_last_item_and_next_position()
            if position == -1:
                return last
            position = position + length
        size = self.repo.array_size
        n = position // size
        i = n * size
        j = i + size
        offset = position - i
        array_id = self.create_array_id(i, j)
        base_array = self.repo[array_id]
        return base_array[offset]

    def get_slice(self, start, stop):
        array_len = self.repo.array_size ** self.repo.array_size

        if start is None:
            start = 0
        elif start < 0:
            start = max(array_len + start, 0)

        if stop is None:
            stop = array_len
        elif stop < 0:
            stop = array_len + stop

        stop = min(stop, array_len)

        size = self.repo.array_size
        while start < stop:
            n = start // size
            i = n * size
            j = i + size
            substart = start - i
            substop = stop - i
            array_id = self.create_array_id(i, j)
            sequence = self.repo[array_id]
            for item in sequence[substart:substop]:
                yield item
            start = j

    def __setitem__(self, position, item):
        # Calculate start and stop position
        # of the containing base array.
        size = self.repo.array_size
        start = (position // size) * size
        stop = start + size

        # Set the item in the base array.
        array_id = self.create_array_id(start, stop)
        array = self.repo[array_id]
        index = position - start
        array[index] = item

        # Calculate the height of the apex of
        # the compound containing given position
        # (zero-based index in big array).
        required_height = self.calc_required_height(position, size)

        # Set array IDs in containing arrays,
        # up to the required height.
        height = 1
        while height < required_height:
            # Set ID of array in its parent array.
            start, stop, height, index_of_child = self.calc_parent(start, stop, height)
            child_id = array_id
            array_id = self.create_array_id(start, stop)
            array = self.repo[array_id]
            try:
                array[index_of_child] = child_id
            except ConcurrencyError:
                return

        # Set the apex to the root array.
        assert array_id
        root = self.repo[self.id]
        try:
            root[required_height - 1] = array_id
        except ConcurrencyError:
            return

    def __len__(self):
        """
        Returns length of array.
        """
        return self.repo.array_size ** self.repo.array_size

    def calc_required_height(self, n, size):
        if size <= 0:
            raise ValueError("Size must be greater than 0")
        capacity = size ** size
        if n + 1 > capacity:
            raise ArrayIndexError("Contents can't be greater than capacity")
        if n == 0 or n == 1:
            return 1
        min_capacity = max(int(size), int(n + 1))
        required_height = log(min_capacity, int(size))
        # Quash numerical error before calling ceil.
        # - this is occasionally required, for example
        #   with base size of 1000 numerical error
        #   makes the required height one greater
        #   than the correct value, which causes
        #   an index error when assigning apex
        #   ID to the root sequence.
        required_height = round(required_height, 10)
        return int(ceil(required_height))

    def calc_parent(self, i, j, h):
        """
        Returns get_big_array and end of span of parent sequence that contains given child.
        """
        N = self.repo.array_size
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

    def create_array_id(self, i, j):
        return uuid5(self.id, str((i, j)))


class AbstractArrayRepository(AbstractEntityRepository):
    """
    Repository for sequence objects.
    """

    def __init__(self, array_size=10000, *args, **kwargs):
        super(AbstractArrayRepository, self).__init__(*args, **kwargs)
        self.array_size = array_size

    def __getitem__(self, array_id):
        """
        Returns sequence for given ID.
        """
        return Array(array_id=array_id, repo=self)


class AbstractBigArrayRepository(AbstractEntityRepository):
    """
    Repository for compound sequence objects.
    """

    @abstractproperty
    def subrepo(self):
        """Sub-sequence repository."""

    def __getitem__(self, array_id):
        """
        Returns sequence for given ID.
        """
        return BigArray(array_id=array_id, repo=self.subrepo)
