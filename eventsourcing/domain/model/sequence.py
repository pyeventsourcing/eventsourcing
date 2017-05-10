from abc import abstractproperty
from uuid import uuid5

import six
from six.moves._thread import get_ident

from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.entity import AbstractEntityRepository, TimestampedVersionedEntity
from eventsourcing.domain.model.events import publish
from eventsourcing.exceptions import CompoundSequenceFullError, ConcurrencyError, SequenceFullError


class SequenceMeta(TimestampedVersionedEntity):
    """
    This class represents an overall, which is
    initially empty. A specialised repository
    SequenceRepo returns a Sequence object which
    can append items to the sequence without
    loading all the events. It can also index,
    slice and iterate through items in the sequence
    without having to load all of them.
    """

    class Event(TimestampedVersionedEntity.Event):
        """Layer supertype."""

    class Started(Event, TimestampedVersionedEntity.Created):
        """Occurs when sequence is started."""

    class ItemAppended(Event):
        """Occurs when item is appended to a sequence."""

    def __init__(self, max_size=None, **kwargs):
        super(SequenceMeta, self).__init__(**kwargs)
        self._max_size = max_size

    @property
    def max_size(self):
        return self._max_size


class CompoundSequenceMeta(SequenceMeta):
    def __init__(self, i=None, j=None, h=None, *args, **kwargs):
        super(CompoundSequenceMeta, self).__init__(*args, **kwargs)
        self._i = i
        self._j = j
        self._h = h

    @property
    def i(self):
        return self._i

    @property
    def j(self):
        return self._j

    @property
    def h(self):
        return self._h


def start_compound_sequence(sequence_id, i, j, h, max_size):
    """
    Factory for Sequence objects.
    
    :rtype: SequenceMeta
    """
    event = CompoundSequenceMeta.Started(originator_id=sequence_id, i=i, j=j, h=h, max_size=max_size)
    entity = CompoundSequenceMeta._mutate(initial=None, event=event)
    publish(event)
    return entity


class Sequence(object):
    def __init__(self, sequence_id, repo, meta=None):
        assert isinstance(repo, AbstractSequenceRepository)
        self.id = sequence_id
        self.repo = repo
        self._meta = meta

    @property
    def meta(self):
        if self._meta is None:
            self._meta = self.repo.get_entity(self.id)
        return self._meta

    def append(self, item, position):
        """
        Appends item to sequence, by publishing an ItemAppended event.

        Won't overrun the end of the sequence, because the position is
        fixed to be less than the max_size, won't overwrite due to OCC.
        """
        size = self.repo.sequence_size
        if size and position >= size:
            raise SequenceFullError
        event = SequenceMeta.ItemAppended(
            originator_id=self.id,
            originator_version=position + 1,
            item=item,
        )
        publish(event)

    def get_position(self):
        last_event = self.repo.event_store.get_most_recent_event(self.id)
        return last_event.originator_version

    def register_sequence(self, sequence_id):
        """
        Factory for Sequence objects.

        :rtype: SequenceMeta
        """
        event = SequenceMeta.Started(originator_id=sequence_id)
        entity = SequenceMeta._mutate(initial=None, event=event)
        publish(event)
        self._meta = entity
        return entity

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
            event = self.repo.event_store.get_domain_event(originator_id=self.id, eq=index + 1)
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
                                                             gte=start_index + 1, limit=limit)
            items = [e.item for e in events]
            return items

    def __len__(self):
        """
        Counts items in sequence.
        """
        event = self.get_last_event()
        if event:
            return event.originator_version
        return 0

    def __repr__(self):
        return "{}(id={})".format(type(self).__name__, self.id)

    def get_last_event(self):
        events = self.repo.event_store.get_domain_events(
            originator_id=self.id,
            limit=1,
            is_ascending=False
        )
        if len(events):
            event = events[0]
            return event

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.id == other.id

    def get_last_and_len(self):
        events = self.repo.event_store.get_domain_events(
            originator_id=self.id,
            limit=1,
            is_ascending=False,
            gt=0,
        )
        if len(events):
            event = events[0]
            return event.item, event.originator_version
        else:
            return None, None

    def register(self):
        self._meta = self.register_sequence(self.id)


class CompoundSequence(Sequence):
    def __init__(self, sequence_id, repo, subrepo):
        assert isinstance(repo, AbstractCompoundSequenceRepository)
        assert isinstance(subrepo, AbstractSequenceRepository)
        super(CompoundSequence, self).__init__(sequence_id=sequence_id, repo=repo)
        self.subrepo = subrepo

    @retry(ConcurrencyError, max_retries=50, wait=0.01)
    def append(self, item, position=None):
        root, height, apex, last, i = self.get_last_sequence()
        assert isinstance(root, Sequence)

        thread_id = get_ident()

        if last is None:
            # print("{} Building root for: {}".format(thread_id, self.id))

            root.register()
            apex_id = self.create_sequence_id(0, self.repo.sequence_size)
            apex = self.subrepo[apex_id]
            apex.register()
            root.append(apex_id, position=0)
            last = apex
        assert isinstance(last, Sequence)
        try:
            position = last.get_position()
            while True:
                ran = 0
                try:
                    last.append(item, position=position)
                    # print("{} Appended item to {} at position {}: {}".format(thread_id, last.id, position, item))
                except ConcurrencyError:
                    # Race forward until it works, or is full, or went a certain distance.
                    position += 1
                    # print("{} Racing forward to position: {} (ran {})".format(thread_id, position, ran))
                    if ran > 10:
                        break
                    else:
                        ran += 1
                else:
                    break
        except SequenceFullError as e:
            if self.repo.sequence_size == 1:
                raise CompoundSequenceFullError
            len_root_sequence = len(root)

            try:
                # This may raise a ConcurrencyError, if another
                # thread has just extended the compound.
                # If so, just let the exception be caught by
                # the retry decorator, so a fresh attempt is
                # made to append the item to the compound sequence.
                sequence_size = self.subrepo.sequence_size
                next_i = i + sequence_size
                # print("{} Extending base for: {}".format(thread_id, next_i))
                next = self.extend_base(next_i, item)

                # If we managed to extend the base, then create a
                # branch. No other thread should be attempting this.
                # So if it fails, the compound will need to be repaired.
                # print("{} Creating detached branch for: {}".format(thread_id, next_i))
                detached_branch_id, target_id, position = self.create_detached_branch(
                    base_id=next.id,
                    i=next_i,
                    max_height=len_root_sequence,
                )

                # If there is a target, then attach the branch to it.
                if target_id:
                    # print("{} Attaching branch for: {}".format(thread_id, next_i))
                    self.attach_branch(target_id, detached_branch_id, position=position)
                # Otherwise demote the top in favour of the branch.
                else:
                    assert apex
                    # print("{} Demoting apex: {}".format(thread_id, apex.id))
                    self.demote(root, apex, height, detached_branch_id)
            except SequenceFullError as e:
                if len(self) == self.subrepo.sequence_size:
                    raise CompoundSequenceFullError
                else:
                    raise e

    def get_last_sequence(self):
        """
        Returns last sequence in compound.

        :rtype: CompoundSequenceReader
        """
        # Get the root sequence (might not have been registered).
        root = self.subrepo[self.id]

        # Get length and last item in the root sequence.
        apex_id, apex_height = root.get_last_and_len()

        # Bail if there isn't anything yet.
        if apex_id is None:
            return root, apex_height, None, None, 0

        # Get the current apex sequence.
        apex = self.subrepo[apex_id]
        assert isinstance(apex, Sequence)

        # Descend into the compound until hitting the bottom.
        sequence = apex
        sequence_i = 0
        height = apex_height
        while height > 1:
            height -= 1
            sequence_id, width = sequence.get_last_and_len()
            assert width > 0
            offset = width - 1
            sequence_i += offset * self.subrepo.sequence_size ** height
            sequence = self.subrepo[sequence_id]

        return root, apex_height, apex, sequence, sequence_i

    def create_sequence_id(self, i, j):
        return uuid5(self.id, str((i, j)))

    def get_last_item_and_n(self):
        _, _, _, sequence, i = self.get_last_sequence()
        item, n = sequence.get_last_and_len()
        return item, i + n - 1

    def extend_base(self, i, item):
        """
        Starts sequence that extends the base of
        the compound, and appends an item to it.

        Starts a new sequence at the bottom of the compound,
        to the right of the right-bottom-most sequence, with a
        span that is contiguous from its left. Then appends the
        given item to it.
        """
        size = self.subrepo.sequence_size
        j = i + size
        sequence_id = self.create_sequence_id(i, j)
        # If may raises a ConcurrencyError.
        meta = self.register_sequence(sequence_id=sequence_id)
        sequence = self.subrepo[sequence_id]
        assert isinstance(sequence, Sequence)
        sequence.append(item, position=0)
        return sequence

    def create_detached_branch(self, base_id, i, max_height):
        """
        Works up from child to parent, building a branch
        that is not attached to the main compound, using
        predictable sequence IDs, attempting to create a
        parent until doing so conflicts with an already
        existing sequence, when it stops and returns the
        branch it has created, or the original child.

        Also return the ID of the already existing parent,
        as target_id, so branch can be attached to it. If
        top of compound is not found, the target_id is None. 
        """
        target_id = None
        sequence_size = self.subrepo.sequence_size
        c_i = i
        c_j = i + sequence_size
        c_h = 1
        top_id = base_id
        while True:
            p_i, p_j, p_h, p_p = self.calc_parent_i_j_h_p(c_i, c_j, c_h)
            if p_h > max_height:
                break
            p_id = self.create_sequence_id(p_i, p_j)
            try:
                parent_meta = self.register_sequence(p_id)
            except ConcurrencyError:
                # It already exists.
                target_id = p_id
                break
            else:
                parent = Sequence(p_id, self.subrepo, parent_meta)
                parent.append(top_id, position=p_p)
                c_i = p_i
                c_j = p_j
                c_h = p_h
                top_id = p_id
        return top_id, target_id, p_p

    def calc_parent_i_j_h_p(self, i, j, h):
        """
        Returns start_root and end of span of parent sequence that contains given child.
        """
        N = self.subrepo.sequence_size
        c_i = i
        c_j = j
        c_h = h
        # Calculate the number of the sequence in its row (sequences
        # with same height), from left to right, starting from 0.
        c_n = c_i // (N ** c_h)
        p_n = c_n // N
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
        # Return parent i, j, h.
        return p_i, p_j, p_h, p_p

    def demote(self, root, old_apex, height, detached_id=None):
        """
        Inserts a new sequence between the root and the current top.

        Starts a new sequence. Appends the current top of the
        compound to it. Optionally appends a detached branch to the
        new sequence, then appends the new sequence to the root.

        :rtype: CompoundSequenceReader
        """
        j = self.subrepo.sequence_size ** (height + 1)
        new_apex_id = self.create_sequence_id(0, j)

        # Will raise ConcurrentError is sequence already exists.
        new_apex_meta = self.register_sequence(new_apex_id)
        new_apex = Sequence(sequence_id=new_apex_id, repo=self.subrepo, meta=new_apex_meta)

        # First, append child to new child.
        new_apex.append(old_apex.id, position=0)
        # Attach new branch.
        if detached_id is not None:
            new_apex.append(detached_id, position=1)
        # Then append new child to to root.
        try:
            root.append(new_apex.id, position=height)
        except SequenceFullError:
            raise CompoundSequenceFullError
        return new_apex

    def attach_branch(self, parent_id, branch_id, position):
        """
        Attaches branch to parent.
        """
        parent = self.subrepo[parent_id]
        # If the calculations are correct, this won't ever raise a ConcurrencyError.
        parent.append(branch_id, position)

    def __getitem__(self, item):
        assert isinstance(item, (six.integer_types, slice))
        # Calculate the i and j of the containing base sequence.
        if isinstance(item, six.integer_types):
            if item >= 0:
                return self.get_item(item)
            else:
                last, n = self.get_last_item_and_n()
                if item == -1:
                    return last
                else:
                    item = n + item + 1
                    return self.get_item(item)
        elif isinstance(item, slice):
            assert item.step in (None, 1), "Slice step must be 1: {}".format(str(item.step))

            sequence_len = None

            if item.start is None:
                start_index = 0
            elif item.start < 0:
                sequence_len = len(self)
                start_index = max(sequence_len + item.start, 0)
            else:
                start_index = item.start

            if not isinstance(item.stop, six.integer_types):
                if sequence_len is None:
                    sequence_len = len(self)
                stop_index = sequence_len
            elif item.stop < 0:
                if sequence_len is None:
                    sequence_len = len(self)
                stop_index = sequence_len + item.stop
            else:
                stop_index = item.stop

            if stop_index <= start_index:
                return []

            return self.get_slice(start_index, stop_index)

    def __len__(self):
        """
        Counts items in compound sequence.
        """
        _, n = self.get_last_item_and_n()
        return n + 1

    def get_item(self, item):
        size = self.subrepo.sequence_size
        n = item // size
        i = n * size
        j = i + size
        offset = item - i
        sequence_id = self.create_sequence_id(i, j)
        sequence = self.subrepo[sequence_id]
        return sequence[offset]

    def get_slice(self, start, stop):
        size = self.subrepo.sequence_size
        while True:
            n = start // size
            i = n * size
            j = i + size
            substart = start - i
            substop = stop - i
            sequence_id = self.create_sequence_id(i, j)
            sequence = self.subrepo[sequence_id]
            for item in sequence[substart:substop]:
                yield item
            start = j
            if start > stop:
                break


class AbstractSequenceRepository(AbstractEntityRepository):
    """
    Repository for sequence objects.
    """

    def __init__(self, sequence_size=10000, *args, **kwargs):
        super(AbstractSequenceRepository, self).__init__(*args, **kwargs)
        self.sequence_size = sequence_size


class AbstractCompoundSequenceRepository(AbstractEntityRepository):
    """
    Repository for compound sequence objects.
    """

    @abstractproperty
    def subrepo(self):
        """Sub-sequence repository."""
