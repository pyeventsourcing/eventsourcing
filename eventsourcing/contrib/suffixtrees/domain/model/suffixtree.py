# coding=utf-8
from __future__ import unicode_literals

import datetime
from uuid import uuid4

from eventsourcing.domain.model.decorators import attribute
from eventsourcing.domain.model.entity import AttributeChanged, Created, Discarded, TimestampedVersionedEntity
from eventsourcing.domain.model.events import publish
from eventsourcing.example.application import ExampleApplication
from eventsourcing.exceptions import RepositoryKeyError
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


class SuffixTree(TimestampedVersionedEntity):
    """A suffix tree for string matching. Uses Ukkonen's algorithm
    for construction.
    """

    class Created(Created):
        pass

    class AttributeChanged(AttributeChanged):
        pass

    class Discarded(Discarded):
        pass

    def __init__(self, root_node_id, case_insensitive=False, **kwargs):
        """
        string
            the string for which to construct a suffix tree
        """
        super(SuffixTree, self).__init__(**kwargs)
        self._root_node_id = root_node_id
        self._case_insensitive = case_insensitive
        self._nodes = {}
        self._edges = {}
        self._N = None
        self._string = None

    @attribute
    def string(self):
        return self._string

    @property
    def N(self):
        return self._N

    @property
    def nodes(self):
        return self._nodes

    @property
    def root_node_id(self):
        return self._root_node_id

    @property
    def edges(self):
        return self._edges

    @property
    def active(self):
        return self._active

    @property
    def case_insensitive(self):
        return self._case_insensitive

    def __repr__(self):
        """
        Lists edges in the suffix tree
        """
        return "SuffixTree({})".format(self.id)

    def add_string(self, string):
        assert self.string is None
        self._active = Suffix(self._root_node_id, 0, -1)
        self._N = len(string) - 1
        if self._case_insensitive:
            string = string.lower()
        self.string = string
        for i in range(len(string)):
            self._add_prefix(i)

    def _add_prefix(self, last_char_index):
        """The core construction method.
        """
        last_parent_node_id = None
        while True:
            parent_node_id = self.active.source_node_id
            if self.active.explicit():
                edge_id = make_edge_id(self.active.source_node_id, self.string[last_char_index])
                if edge_id in self.edges:
                    # prefix is already in tree
                    break
            else:
                edge_id = make_edge_id(self.active.source_node_id, self.string[self.active.first_char_index])
                e = self.edges[edge_id]
                if self.string[e.first_char_index + self.active.length + 1] == self.string[last_char_index]:
                    # prefix is already in tree
                    break
                parent_node_id = self._split_edge(e, self.active)

            node = register_new_node()
            self.nodes[node.id] = node
            edge_id = make_edge_id(parent_node_id, self.string[last_char_index])
            e = register_new_edge(
                edge_id=edge_id,
                first_char_index=last_char_index,
                last_char_index=self.N,
                source_node_id=parent_node_id,
                dest_node_id=node.id,
            )
            self._insert_edge(e)

            if last_parent_node_id is not None:
                self.nodes[last_parent_node_id].suffix_node_id = parent_node_id
            last_parent_node_id = parent_node_id

            if self.active.source_node_id == self.root_node_id:
                self.active.first_char_index += 1
            else:
                self.active.source_node_id = self.nodes[self.active.source_node_id].suffix_node_id
            self._canonize_suffix(self.active)
        if last_parent_node_id is not None:
            self.nodes[last_parent_node_id].suffix_node_id = parent_node_id
        self.active.last_char_index += 1
        self._canonize_suffix(self.active)

    def _insert_edge(self, edge):
        edge_id = make_edge_id(edge.source_node_id, self.string[edge.first_char_index])
        self.edges[edge_id] = edge

    def _remove_edge(self, edge):
        edge_id = make_edge_id(edge.source_node_id, self.string[edge.first_char_index])
        self.edges.pop(edge_id)

    def _split_edge(self, first_edge, suffix):
        assert isinstance(first_edge, Edge)
        assert isinstance(suffix, Suffix)

        # Create a middle node that will split the edge.
        new_node = register_new_node(suffix.source_node_id)
        self.nodes[new_node.id] = new_node

        # Split the char indexes.
        first_edge_last_char_index = first_edge.first_char_index + suffix.length
        second_edge_first_char_index = first_edge.first_char_index + suffix.length + 1
        second_edge_last_char_index = first_edge.last_char_index

        # Create a new edge, from the middle node to the original destination.
        second_edge_id = make_edge_id(new_node.id, self.string[first_edge.first_char_index + suffix.length + 1])
        second_edge = register_new_edge(
            edge_id=second_edge_id,
            first_char_index=second_edge_first_char_index,
            last_char_index=second_edge_last_char_index,
            source_node_id=new_node.id,
            dest_node_id=first_edge.dest_node_id,
        )
        self._insert_edge(second_edge)

        # Shorten the first edge.
        first_edge.last_char_index = first_edge_last_char_index
        first_edge.dest_node_id = new_node.id

        # Return middle node.
        return new_node.id

    def _canonize_suffix(self, suffix):
        """This canonizes the suffix, walking along its suffix string until it
        is explicit or there are no more matched nodes.
        """
        if not suffix.explicit():
            edge_id = make_edge_id(suffix.source_node_id, self.string[suffix.first_char_index])
            e = self.edges[edge_id]
            if e.length <= suffix.length:
                suffix.first_char_index += e.length + 1
                suffix.source_node_id = e.dest_node_id
                self._canonize_suffix(suffix)


class Node(TimestampedVersionedEntity):
    """A node in the suffix tree.
    """

    class Created(Created): pass

    class AttributeChanged(AttributeChanged): pass

    class Discarded(Discarded): pass

    def __init__(self, suffix_node_id=None, *args, **kwargs):
        super(Node, self).__init__(*args, **kwargs)
        self._suffix_node_id = suffix_node_id

    @attribute
    def suffix_node_id(self):
        """The id of a node with a matching suffix, representing a suffix link.

        None indicates this node has no suffix link.
        """
        return self._suffix_node_id

    def __repr__(self):
        return "Node(suffix link: %d)" % self.suffix_node_id


class Edge(TimestampedVersionedEntity):
    """An edge in the suffix tree.
    """

    class Created(Created): pass

    class AttributeChanged(AttributeChanged): pass

    class Discarded(Discarded): pass

    def __init__(self, first_char_index, last_char_index, source_node_id, dest_node_id, **kwargs):
        super(Edge, self).__init__(**kwargs)
        self._first_char_index = first_char_index
        self._last_char_index = last_char_index
        self._source_node_id = source_node_id
        self._dest_node_id = dest_node_id

    @attribute
    def first_char_index(self):
        """Index of start of string part represented by this edge.
        """
        return self._first_char_index

    @attribute
    def last_char_index(self):
        """Index of end of string part represented by this edge.
        """
        return self._last_char_index

    @attribute
    def source_node_id(self):
        """Id of source node of edge.
        """
        return self._source_node_id

    @attribute
    def dest_node_id(self):
        """Id of destination node of edge.
        """
        return self._dest_node_id

    @property
    def length(self):
        """Number of chars in the string part represented by this edge.
        """
        return self.last_char_index - self.first_char_index

    def __repr__(self):
        return 'Edge(%d, %d, %d, %d)' % (self.source_node_id, self.dest_node_id
                                         , self.first_char_index, self.last_char_index)


class Suffix(object):
    """Represents a suffix from first_char_index to last_char_index.
    """

    def __init__(self, source_node_id, first_char_index, last_char_index):
        self._source_node_id = source_node_id
        self._first_char_index = first_char_index
        self._last_char_index = last_char_index

    @property
    def source_node_id(self):
        """Index of node where this suffix starts.
        """
        return self._source_node_id

    @source_node_id.setter
    def source_node_id(self, value):
        self._source_node_id = value

    @property
    def first_char_index(self):
        """Index of start of suffix in string.
        """
        return self._first_char_index

    @first_char_index.setter
    def first_char_index(self, value):
        self._first_char_index = value

    @property
    def last_char_index(self):
        """Index of end of suffix in string.
        """
        return self._last_char_index

    @last_char_index.setter
    def last_char_index(self, value):
        self._last_char_index = value

    @property
    def length(self):
        """Number of chars in string.
        """
        return self.last_char_index - self.first_char_index

    def explicit(self):
        """A suffix is explicit if it ends on a node. first_char_index
        is set greater than last_char_index to indicate this.
        """
        return self.first_char_index > self.last_char_index

    def implicit(self):
        return self.last_char_index >= self.first_char_index


# Factory methods.

def register_new_node(suffix_node_id=None):
    """Factory method, registers new node.
    """
    node_id = uuid4()
    event = Node.Created(originator_id=node_id, suffix_node_id=suffix_node_id)
    entity = Node.mutate(event=event)
    publish(event)
    return entity


def make_edge_id(source_node_index, first_char):
    """Returns a string made from given params.
    """
    return "{}::{}".format(source_node_index, first_char)


def register_new_edge(edge_id, first_char_index, last_char_index, source_node_id, dest_node_id):
    """Factory method, registers new edge.
    """
    event = Edge.Created(
        originator_id=edge_id,
        first_char_index=first_char_index,
        last_char_index=last_char_index,
        source_node_id=source_node_id,
        dest_node_id=dest_node_id,
    )
    entity = Edge.mutate(event=event)
    publish(event)
    return entity


def register_new_suffix_tree(case_insensitive=False):
    """Factory method, returns new suffix tree object.
    """
    assert isinstance(case_insensitive, bool)
    root_node = register_new_node()

    suffix_tree_id = uuid4()
    event = SuffixTree.Created(
        originator_id=suffix_tree_id,
        root_node_id=root_node.id,
        case_insensitive=case_insensitive,
    )
    entity = SuffixTree.mutate(event=event)

    assert isinstance(entity, SuffixTree)

    entity.nodes[root_node.id] = root_node

    publish(event)

    return entity


# Domain services

def find_substring(substring, suffix_tree, edge_repo):
    """Returns the index if substring in tree, otherwise -1.
    """
    assert isinstance(substring, str)
    assert isinstance(suffix_tree, SuffixTree)
    assert isinstance(edge_repo, EventSourcedRepository)
    if not substring:
        return -1
    if suffix_tree.case_insensitive:
        substring = substring.lower()
    curr_node_id = suffix_tree.root_node_id
    i = 0
    while i < len(substring):
        edge_id = make_edge_id(curr_node_id, substring[i])
        try:
            edge = edge_repo[edge_id]
        except RepositoryKeyError:
            return -1
        ln = min(edge.length + 1, len(substring) - i)
        if substring[i:i + ln] != suffix_tree.string[edge.first_char_index:edge.first_char_index + ln]:
            return -1
        i += edge.length + 1
        curr_node_id = edge.dest_node_id
    return edge.first_char_index - len(substring) + ln


def has_substring(substring, suffix_tree, edge_repo):
    return find_substring(substring, suffix_tree, edge_repo) != -1


class SuffixTreeApplication(ExampleApplication):

    def register_new_suffixtree(self, case_insensitive=False):
        return register_new_suffix_tree(case_insensitive)

    def find_substring(self, substring, suffix_tree_id):
        suffix_tree = self.example_repository[suffix_tree_id]
        started = datetime.datetime.now()
        result = find_substring(substring=substring, suffix_tree=suffix_tree, edge_repo=self.example_repository)
        print("- found substring '{}' in: {}".format(substring, datetime.datetime.now() - started))
        return result

    def has_substring(self, substring, suffix_tree_id):
        suffix_tree = self.example_repository[suffix_tree_id]
        return has_substring(
            substring=substring,
            suffix_tree=suffix_tree,
            edge_repo=self.example_repository,
        )
