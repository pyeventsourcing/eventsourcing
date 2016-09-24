# coding=utf-8
from __future__ import unicode_literals

from uuid import uuid4

import six

from eventsourcing.domain.model.entity import EventSourcedEntity, mutableproperty, EntityRepository
from eventsourcing.domain.model.events import publish


class SuffixTree(EventSourcedEntity):
    """A suffix tree for string matching. Uses Ukkonen's algorithm
    for construction.
    """

    class Created(EventSourcedEntity.Created):
        pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged):
        pass

    class Discarded(EventSourcedEntity.Discarded):
        pass

    def __init__(self, string, case_insensitive=False, **kwargs):
        """
        string
            the string for which to construct a suffix tree
        """
        super(SuffixTree, self).__init__(**kwargs)
        self._string = string
        self._case_insensitive = case_insensitive
        self._N = len(string) - 1
        node = register_new_node()
        self._nodes = {
            node.id: node
        }
        self._root_node_id = node.id
        self._edges = {}
        self._active = Suffix(self._root_node_id, 0, -1)
        if self._case_insensitive:
            self._string = self._string.lower()
        for i in range(len(string)):
            self._add_prefix(i)

    @property
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
        curr_index = self.N
        s = "\tStart \tEnd \tSuf \tFirst \tLast \tString\n"
        values = self.edges.values()
        values.sort(key=lambda x: x.source_node_id)
        for edge in values:
            if edge.source_node_id == None:
                continue
            s += "\t%s \t%s \t%s \t%s \t%s \t" % (edge.source_node_id
                                                  , edge.dest_node_id
                                                  , self.nodes[edge.dest_node_id].suffix_node_id
                                                  , edge.first_char_index
                                                  , edge.last_char_index)

            top = min(curr_index, edge.last_char_index)
            s += self.string[edge.first_char_index:top + 1] + "\n"
        return s

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
            label = self.string[last_char_index:self.N + 1]
            e = register_new_edge(
                edge_id=edge_id,
                label=label,
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
        edge_id = make_edge_id(edge.source_node_id, edge.label[0])
        self.edges[edge_id] = edge

    def _remove_edge(self, edge):
        edge_id = make_edge_id(edge.source_node_id, edge.label[0])
        self.edges.pop(edge_id)

    def _split_edge(self, first_edge, suffix):
        assert isinstance(first_edge, Edge)
        assert isinstance(suffix, Suffix)

        # Create a middle node that will split the edge.
        new_node = register_new_node(suffix.source_node_id)
        self.nodes[new_node.id] = new_node

        # Split the label.
        first_label = first_edge.label[:suffix.length + 1]
        second_label = first_edge.label[suffix.length + 1:]

        # Split the char indexes.
        first_edge_last_char_index = first_edge.first_char_index + suffix.length
        second_edge_first_char_index = first_edge.first_char_index + suffix.length + 1
        second_edge_last_char_index = first_edge.last_char_index

        # Create a new edge, from the middle node to the original destination.
        second_edge_id = make_edge_id(new_node.id, second_label[0])
        second_edge = register_new_edge(
            edge_id=second_edge_id,
            label=second_label,
            first_char_index=second_edge_first_char_index,
            last_char_index=second_edge_last_char_index,
            source_node_id=new_node.id,
            dest_node_id=first_edge.dest_node_id,
        )
        self._insert_edge(second_edge)

        # Shorten the first edge.
        first_edge.label = first_label
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


class Node(EventSourcedEntity):
    """A node in the suffix tree.
    """

    class Created(EventSourcedEntity.Created): pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged): pass

    class Discarded(EventSourcedEntity.Discarded): pass

    def __init__(self, suffix_node_id=None, *args, **kwargs):
        super(Node, self).__init__(*args, **kwargs)
        self._suffix_node_id = suffix_node_id

    @mutableproperty
    def suffix_node_id(self):
        """The id of a node with a matching suffix, representing a suffix link.

        None indicates this node has no suffix link.
        """
        return self._suffix_node_id

    def __repr__(self):
        return "Node(suffix link: %d)" % self.suffix_node_id


class Edge(EventSourcedEntity):
    """An edge in the suffix tree.
    """

    class Created(EventSourcedEntity.Created): pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged): pass

    class Discarded(EventSourcedEntity.Discarded): pass

    def __init__(self, label, first_char_index, last_char_index, source_node_id, dest_node_id, **kwargs):
        super(Edge, self).__init__(**kwargs)
        self._label = label
        self._first_char_index = first_char_index
        self._last_char_index = last_char_index
        self._source_node_id = source_node_id
        self._dest_node_id = dest_node_id

    @mutableproperty
    def label(self):
        """String part represented by this edge.
        """
        return self._label

    @mutableproperty
    def first_char_index(self):
        """Index of start of string part represented by this edge.
        """
        return self._first_char_index

    @mutableproperty
    def last_char_index(self):
        """Index of end of string part represented by this edge.
        """
        return self._last_char_index

    @mutableproperty
    def source_node_id(self):
        """Id of source node of edge.
        """
        return self._source_node_id

    @mutableproperty
    def dest_node_id(self):
        """Id of destination node of edge.
        """
        return self._dest_node_id

    @property
    def length(self):
        """Number of chars in the string part represented by this edge.
        """
        return len(self.label) - 1

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
    node_id = uuid4().hex
    event = Node.Created(entity_id=node_id, suffix_node_id=suffix_node_id)
    entity = Node.mutate(event=event)
    publish(event)
    return entity


def make_edge_id(source_node_index, first_char):
    """Returns a string made from given params.
    """
    return "{}::{}".format(source_node_index, first_char)


def register_new_edge(edge_id, label, first_char_index, last_char_index, source_node_id, dest_node_id):
    """Factory method, registers new edge.
    """
    event = Edge.Created(
        entity_id=edge_id,
        label=label,
        first_char_index=first_char_index,
        last_char_index=last_char_index,
        source_node_id=source_node_id,
        dest_node_id=dest_node_id,
    )
    entity = Edge.mutate(event=event)
    publish(event)
    return entity


def register_new_suffix_tree(string, case_insensitive=False):
    """Factory method, returns new suffix tree object.
    """
    suffix_tree_id = uuid4().hex
    event = SuffixTree.Created(
        entity_id=suffix_tree_id,
        string=string,
        case_insensitive=case_insensitive,
    )
    entity = SuffixTree.mutate(event=event)
    publish(event)
    return entity


# Repositories.

class SuffixTreeRepository(EntityRepository):
    pass


class NodeRepository(EntityRepository):
    pass


class EdgeRepository(EntityRepository):
    pass


# Domain services

def find_substring(substring, suffix_tree, edge_repo):
    """Returns the index if substring in tree, otherwise -1.
    """
    assert isinstance(substring, six.string_types)
    assert isinstance(suffix_tree, SuffixTree)
    assert isinstance(edge_repo, EdgeRepository)
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
        except KeyError:
            return -1
        ln = min(edge.length + 1, len(substring) - i)
        if substring[i:i + ln] != edge.label[:ln]:
            return -1
        i += edge.length + 1
        curr_node_id = edge.dest_node_id
    return edge.first_char_index - len(substring) + ln


def has_substring(substring, suffix_tree, edge_repo):
    return find_substring(substring, suffix_tree, edge_repo) != -1
