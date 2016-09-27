# coding=utf-8
from __future__ import unicode_literals

import datetime
from collections import OrderedDict
from uuid import uuid4

from singledispatch import singledispatch
import six

from eventsourcing.domain.model.entity import EventSourcedEntity, mutableproperty, EntityRepository, entity_mutator
from eventsourcing.domain.model.events import publish, DomainEvent

# Use a private code point to terminate the string IDs.
STRING_ID_END = '\uEFFF'


class SuffixTreeGeneralized(EventSourcedEntity):
    """A suffix tree for string matching. Uses Ukkonen's algorithm
    for construction.
    """

    class Created(EventSourcedEntity.Created):
        pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged):
        pass

    class Discarded(EventSourcedEntity.Discarded):
        pass

    def __init__(self, root_node_id, case_insensitive=False, **kwargs):
        super(SuffixTreeGeneralized, self).__init__(**kwargs)
        self._root_node_id = root_node_id
        self._case_insensitive = case_insensitive
        self._nodes = {}
        self._edges = {}
        self._N = None
        self._string = None
        self._active = None
        self._node_repo = None
        self._edge_repo = None

    @mutableproperty
    def string(self):
        return self._string

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
        return 'SuffixTreeGeneralized(id={})'.format(self.id)
        # Todo: Something that shows the actual tree.

    def add_string(self, string, string_id):
        assert isinstance(string_id, six.string_types)
        assert self._root_node_id is not None
        self._active = Suffix(self._root_node_id, 0, -1)
        if self._case_insensitive:
            string = string.lower()
        assert STRING_ID_END not in string_id
        assert STRING_ID_END not in string

        # Append the string ID to the string.
        string += u"{}{}".format(string_id, STRING_ID_END)

        # Remember the string.
        self.string = string

        # Remember the length of the string.
        self._N = len(string)

        # Add each suffix.
        for i in range(len(string)):
            self._add_prefix(i, string, string_id)

    def _add_prefix(self, i, string, string_id):
        """The core construction method.
        """
        last_parent_node = None
        while True:
            parent_node_id = self.active.source_node_id
            if self.active.explicit():
                # Break if prefix is already in tree.
                edge_id = make_edge_id(self.active.source_node_id, string[i])
                try:
                    e = self.get_edge(edge_id)
                except KeyError:
                    pass
                else:
                    dest_node = self.get_node(e.dest_node_id)
                    if dest_node.string_id is None:
                        # pass
                        dest_node.string_id = string_id
                    else:
                        break
                    # break
            else:
                # Break if prefix is already in tree.
                edge_id = make_edge_id(self.active.source_node_id, string[self.active.first_char_index])
                e = self.get_edge(edge_id)
                if e.label[self.active.length + 1] == string[i]:
                    dest_node = self.get_node(e.dest_node_id)
                    # if not dest_node.string_id:
                    # #     pass
                    #     dest_node.string_id = string_id
                    # else:
                    #     break
                    break

                # Split the edge, with a new middle node that will be the parent node.
                parent_node_id = self._split_edge(e, self.active)

            edge_id = make_edge_id(parent_node_id, string[i])
            parent_node = self.get_node(parent_node_id)
            try:
                e = self.get_edge(edge_id)
            except KeyError:
                # Make a new leaf node, with the string ID.
                node = register_new_node(string_id=string_id)
                self._cache_node(node)

                # Make a label for the edge to the leaf, using the suffix of the string from i onwards.
                label = string[i:]

                # Make a new edge to the new leaf node, from the parent node.
                e = register_new_edge(
                    label=label,
                    edge_id=edge_id,
                    source_node_id=parent_node_id,
                    dest_node_id=node.id,
                )
                # Register the new leaf node as a child node of the parent node.
                parent_node.add_child_node_id(node.id, e.length + 1)
                self._cache_edge(e)

            # Unless parent is root, set the last parent's suffix
            # node as the current parent's suffix node.
            if last_parent_node is not None:
                last_parent_node.suffix_node_id = parent_node_id
            last_parent_node = parent_node

            # Move to the next shortest suffix along by one.
            if self.active.source_node_id == self.root_node_id:
                self.active.first_char_index += 1
            else:
                self.active.source_node_id = self.get_node(self.active.source_node_id).suffix_node_id

            self._canonize_suffix(self.active, string)

        if last_parent_node is not None:
            last_parent_node.suffix_node_id = parent_node_id
        self.active.last_char_index += 1
        self._canonize_suffix(self.active, string)

        # If we're re-adding a string, we need to set the string ID.
        node = self.get_node(self.active.source_node_id)
        if node.string_id is not None:
            node.string_id = string_id

    def remove_string(self, string, string_id):
        assert isinstance(string_id, six.string_types)
        if self._case_insensitive:
            string = string.lower()
        assert STRING_ID_END not in string_id
        assert STRING_ID_END not in string
        string += u"{}{}".format(string_id, STRING_ID_END)
        self._N = len(string) - 1
        self.string = string
        for i in range(len(string)):

            # Walk down the tree.
            suffix = Suffix(self.root_node_id, i, self._N)
            self._canonize_suffix(suffix, string)

            leaf_node = self.get_node(suffix.source_node_id)
            assert isinstance(leaf_node, SuffixTreeNode)

            # For now, just set the string_id to None.
            if leaf_node.string_id == string_id:
                leaf_node.string_id = None


        # Todo: Remove all leaf nodes with string_id, either by collecting all the nodes when they are
        # Todo: created or by walking the tree using the string and discovering the leaf nodes all over again.
        # Todo: The problem with going after the leaf nodes directly is there aren't currently any links up the treee
        # Todo: so maybe a node could have a parent node ID, that gets updated when an edge is split, which is used
        # Todo: to remove inner nodes that are no longer needed.
        # Todo: Also remove edges to the node.
        # Todo: Also remove inner nodes that have no children because a leaf or inner node was removed.
        # Todo: Also remove edges to removed inner nodes.
        # Todo: Also remove any removed nodes from collections of children.
        # Todo: Also remove any nodes that only have one child, because they were a branch that is no longer needed,
        # Todo: but connect that child to the removed node's parent with an edge, and add it to parent's collection of child nodes.

    def get_edge(self, edge_id):
        # Raises KeyError is not found because this method was factored out from various places that
        # used the repo directly and so expected a KeyError to be raised if edge is not in repo.
        if not self._edge_repo:
            return self.edges[edge_id]
        try:
            return self.edges[edge_id]
        except KeyError as e:
            try:
                edge = self._edge_repo[edge_id]
            except KeyError:
                raise e
            else:
                self._cache_edge(edge)
                return edge

    def has_edge(self, edge_id):
        try:
            return self.get_edge(edge_id)
        except KeyError:
            pass

    def get_node(self, node_id):
        # Raises KeyError is not found because this method was factored out from various places that
        # used the repo directly and so expected a KeyError to be raised if node is not in repo.
        if not self._node_repo:
            return self.nodes[node_id]
        try:
            return self.nodes[node_id]
        except KeyError as e:
            try:
                node = self._node_repo[node_id]
            except KeyError:
                raise e
            else:
                self._cache_node(node)
                return node

    def _cache_node(self, node):
        self.nodes[node.id] = node

    def _cache_edge(self, edge):
        edge_id = make_edge_id(edge.source_node_id, edge.label[0])
        self.edges[edge_id] = edge

    def _split_edge(self, first_edge, suffix):
        assert isinstance(first_edge, SuffixTreeEdge)
        assert isinstance(suffix, Suffix)

        # Create a new middle node that will split the edge.
        new_middle_node = register_new_node(suffix_node_id=suffix.source_node_id)
        self._cache_node(new_middle_node)

        # Split the label.
        first_label = first_edge.label[:suffix.length + 1]
        second_label = first_edge.label[suffix.length + 1:]

        # Create a new edge, from the new middle node to the original destination.
        second_edge_id = make_edge_id(source_node_id=new_middle_node.id, first_char=second_label[0])
        original_dest_node_id = first_edge.dest_node_id
        second_edge = register_new_edge(
            label=second_label,
            edge_id=second_edge_id,
            source_node_id=new_middle_node.id,
            dest_node_id=original_dest_node_id,
        )
        self._cache_edge(second_edge)

        # Add the original dest node as a child of the new middle node.
        new_middle_node.add_child_node_id(original_dest_node_id, second_edge.length + 1)

        # Shorten the first edge.
        first_edge.label = first_label
        first_edge.dest_node_id = new_middle_node.id

        # Remove the original dest node from the children of the original
        # source node, and add the new middle node to the children.
        original_source_node = self.get_node(first_edge.source_node_id)
        original_source_node.remove_child_node_id(original_dest_node_id)
        original_source_node.add_child_node_id(new_middle_node.id, first_edge.length + 1)

        # Return middle node.
        return new_middle_node.id

    def _canonize_suffix(self, suffix, string):
        """This canonizes the suffix, walking along its suffix string until it
        is explicit or there are no more matched nodes.
        """
        if not suffix.explicit():
            if len(string) < suffix.first_char_index + 1:
                raise AssertionError
            edge_id = make_edge_id(suffix.source_node_id, string[suffix.first_char_index])
            e = self.get_edge(edge_id)
            if e.length <= suffix.length:
                suffix.first_char_index += e.length + 1
                suffix.source_node_id = e.dest_node_id
                self._canonize_suffix(suffix, string)


class SuffixTreeNode(EventSourcedEntity):
    """A node in the suffix tree.
    """

    class Created(EventSourcedEntity.Created): pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged): pass

    class Discarded(EventSourcedEntity.Discarded): pass

    class ChildNodeAdded(DomainEvent): pass

    class ChildNodeRemoved(DomainEvent): pass

    def __init__(self, suffix_node_id=None, string_id=None, *args, **kwargs):
        super(SuffixTreeNode, self).__init__(*args, **kwargs)
        self._suffix_node_id = suffix_node_id
        self._string_id = string_id
        self._child_node_ids = OrderedDict()

    @mutableproperty
    def suffix_node_id(self):
        """The id of a node with a matching suffix, representing a suffix link.

        None indicates this node has no suffix link.
        """

    @mutableproperty
    def string_id(self):
        """The id of a string being added to the generalised suffix tree when this node was created.
        """

    def __repr__(self):
        return "SuffixTreeNode(suffix link: {})".format(self.suffix_node_id)

    def add_child_node_id(self, child_node_id, edge_len):
        event = SuffixTreeNode.ChildNodeAdded(
            entity_id=self.id,
            entity_version=self.version,
            child_node_id=child_node_id,
            edge_len=edge_len,
        )
        self._apply(event)
        publish(event)

    def remove_child_node_id(self, child_node_id):
        event = SuffixTreeNode.ChildNodeRemoved(
            entity_id=self.id,
            entity_version=self.version,
            child_node_id=child_node_id,
        )
        self._apply(event)
        publish(event)

    @staticmethod
    def _mutator(event, initial):
        return suffix_tree_node_mutator(event, initial)


@singledispatch
def suffix_tree_node_mutator(event, initial):
    return entity_mutator(event, initial)

@suffix_tree_node_mutator.register(SuffixTreeNode.ChildNodeAdded)
def child_node_added_mutator(event, self):
    assert isinstance(self, SuffixTreeNode), self
    self._child_node_ids[event.child_node_id] = event.edge_len
    self._increment_version()
    return self


@suffix_tree_node_mutator.register(SuffixTreeNode.ChildNodeRemoved)
def child_node_removed_mutator(event, self):
    assert isinstance(self, SuffixTreeNode), self
    try:
        del(self._child_node_ids[event.child_node_id])
    except KeyError:
        pass
    self._increment_version()
    return self


class SuffixTreeEdge(EventSourcedEntity):
    """An edge in the suffix tree.
    """

    class Created(EventSourcedEntity.Created): pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged): pass

    class Discarded(EventSourcedEntity.Discarded): pass

    def __init__(self, label, source_node_id, dest_node_id, **kwargs):
        super(SuffixTreeEdge, self).__init__(**kwargs)
        self._label = label
        self._source_node_id = source_node_id
        self._dest_node_id = dest_node_id

    @mutableproperty
    def label(self):
        """Index of start of string part represented by this edge.
        """
        return self._label

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
        return 'SuffixTreeEdge({}, {}, {})'.format(self.source_node_id, self.dest_node_id, self.label)


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

def register_new_node(suffix_node_id=None, string_id=None):
    """Factory method, registers new node.
    """
    node_id = uuid4().hex
    event = SuffixTreeNode.Created(
        entity_id=node_id,
        suffix_node_id=suffix_node_id,
        string_id=string_id,
    )
    entity = SuffixTreeNode.mutate(event=event)
    publish(event)
    return entity


def make_edge_id(source_node_id, first_char):
    """Returns a string made from given params.
    """
    # assert STRING_ID_PADDING_RIGHT not in first_char
    # assert STRING_ID_PADDING_RIGHT not in source_node_id
    return "{}::{}".format(source_node_id, first_char)


def register_new_edge(edge_id, label, source_node_id, dest_node_id):
    """Factory method, registers new edge.
    """
    event = SuffixTreeEdge.Created(
        entity_id=edge_id,
        label=label,
        source_node_id=source_node_id,
        dest_node_id=dest_node_id,
    )
    entity = SuffixTreeEdge.mutate(event=event)
    publish(event)
    return entity


def register_new_suffix_tree(string=None, string_id=None, case_insensitive=False):
    """Factory method, returns new suffix tree object.
    """
    root_node = register_new_node()

    suffix_tree_id = uuid4().hex
    event = SuffixTreeGeneralized.Created(
        entity_id=suffix_tree_id,
        root_node_id=root_node.id,
        case_insensitive=case_insensitive,
    )
    entity = SuffixTreeGeneralized.mutate(event=event)

    assert isinstance(entity, SuffixTreeGeneralized)

    entity.nodes[root_node.id] = root_node

    publish(event)

    if string is not None:
        assert string_id
        entity.add_string(string, string_id)

    return entity


# Repositories.

class SuffixTreeGeneralizedRepository(EntityRepository):
    pass


class NodeRepository(EntityRepository):
    pass


class EdgeRepository(EntityRepository):
    pass


# Domain services

def find_substring_edge(substring, suffix_tree, edge_repo):
    """Returns the last edge, if substring in tree, otherwise None.
    """
    assert isinstance(substring, six.string_types)
    assert isinstance(suffix_tree, SuffixTreeGeneralized)
    assert isinstance(edge_repo, EdgeRepository)
    if not substring:
        return None, None
    if suffix_tree.case_insensitive:
        substring = substring.lower()
    curr_node_id = suffix_tree.root_node_id
    i = 0
    while i < len(substring):
        edge_id = make_edge_id(curr_node_id, substring[i])
        try:
            edge = edge_repo[edge_id]
        except KeyError:
            return None, None
        ln = min(edge.length + 1, len(substring) - i)
        if substring[i:i + ln] != edge.label[:ln]:
            return None, None
        i += edge.length + 1
        curr_node_id = edge.dest_node_id
    return edge, ln


def has_substring(substring, suffix_tree, edge_repo):
    edge, ln = find_substring_edge(substring, suffix_tree, edge_repo)
    return edge is not None


# Application
from eventsourcing.application.example.with_cassandra import ExampleApplicationWithCassandra
from eventsourcing.infrastructure.event_sourced_repos.collection_repo import CollectionRepo
from eventsourcing.infrastructure.event_sourced_repos.suffixtreegeneralized_repo import SuffixTreeGeneralizedRepo, NodeRepo, EdgeRepo

class SuffixTreeApplication(ExampleApplicationWithCassandra):

    def __init__(self, **kwargs):
        super(SuffixTreeApplication, self).__init__(**kwargs)
        self.suffix_tree_repo = SuffixTreeGeneralizedRepo(self.event_store)
        self.node_repo = NodeRepo(self.event_store)
        self.edge_repo = EdgeRepo(self.event_store)
        self.collections = CollectionRepo(self.event_store)

    def register_new_suffixtree(self, string, case_insensitive=False):
        return register_new_suffix_tree(string, case_insensitive)

    def get_suffix_tree(self, suffix_tree_id):
        suffix_tree = self.suffix_tree_repo[suffix_tree_id]
        suffix_tree._node_repo = self.node_repo
        suffix_tree._edge_repo = self.edge_repo
        return suffix_tree

    def find_strings(self, substring, suffix_tree_id, limit=None):
        edge, ln = self.find_substring_edge(substring=substring, suffix_tree_id=suffix_tree_id)
        if edge is None:
            return []

        leaf_nodes = get_leaf_nodes(edge.dest_node_id, self.node_repo, edge.length + 1 - ln, uniques=set(), limit=limit)

        return [l.string_id for l in leaf_nodes]

    def find_substring_edge(self, substring, suffix_tree_id):
        suffix_tree = self.suffix_tree_repo[suffix_tree_id]
        started = datetime.datetime.now()
        edge, ln = find_substring_edge(substring=substring, suffix_tree=suffix_tree, edge_repo=self.edge_repo)
        print("- found substring '{}' in: {}".format(substring, datetime.datetime.now() - started))
        return edge, ln

    def has_substring(self, substring, suffix_tree_id):
        suffix_tree = self.suffix_tree_repo[suffix_tree_id]
        return has_substring(
            substring=substring,
            suffix_tree=suffix_tree,
            edge_repo=self.edge_repo,
        )


# Todo: Change this to be a loop rather than reentrant.
# Find all leaf nodes under the given node (nodes with zero child nodes).
def get_leaf_nodes(node_id, node_repo, length_until_end=0, edge_length=0, uniques=None, limit=None):
    length_until_end = length_until_end + edge_length
    node = node_repo[node_id]
    assert isinstance(node, SuffixTreeNode)

    # If it's a leaf node...
    if not node._child_node_ids:
        if node.string_id is None:
            raise StopIteration

        # Check we don't already have this one.
        if node.string_id not in uniques:
            # Check the match isn't part of the appended string ID.
            if len(node.string_id) + len(STRING_ID_END) <= length_until_end:
                uniques.add(node.string_id)
                yield node
                if limit is not None and len(uniques) >= limit:
                    raise StopIteration
    # Otherwise recurse down into the tree.
    else:
        for (child_node_id, edge_length) in node._child_node_ids.items():
            leaf_nodes = get_leaf_nodes(node_id=child_node_id, node_repo=node_repo, length_until_end=length_until_end,
                                        edge_length=edge_length, uniques=uniques, limit=limit)
            for leaf in leaf_nodes:
                yield leaf
                if limit is not None and len(uniques) >= limit:
                    raise StopIteration

