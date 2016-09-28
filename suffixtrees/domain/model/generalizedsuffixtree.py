# coding=utf-8
from __future__ import unicode_literals

from collections import OrderedDict
from uuid import uuid4

import six
from singledispatch import singledispatch

from eventsourcing.domain.model.entity import EventSourcedEntity, mutableproperty, EntityRepository, entity_mutator
from eventsourcing.domain.model.events import publish, DomainEvent

# Use a private code point to terminate the string IDs.
STRING_ID_END = '\uEFFF'


class GeneralizedSuffixTree(EventSourcedEntity):
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
        super(GeneralizedSuffixTree, self).__init__(**kwargs)
        self._root_node_id = root_node_id
        self._case_insensitive = case_insensitive
        self._nodes = {}
        self._edges = {}
        self._string = None
        self._suffix = None
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
    def suffix(self):
        return self._suffix

    @property
    def case_insensitive(self):
        return self._case_insensitive

    def __repr__(self):
        """
        Lists edges in the suffix tree
        """
        # Todo: Something that shows the actual tree.
        return 'GeneralizedSuffixTree(id={})'.format(self.id)

    def add_string(self, string, string_id):
        assert isinstance(string, six.string_types)
        assert isinstance(string_id, six.string_types)

        # Create "active" suffix object.
        self._suffix = Suffix(self._root_node_id, 0, -1)

        # Lower the string, if it's a case insensitive tree.
        if self._case_insensitive:
            string = string.lower()
        assert STRING_ID_END not in string_id
        assert STRING_ID_END not in string

        # Append the (hopefully unique) string ID to the string.
        string_extended = u"{}{}{}".format(string, string_id, STRING_ID_END)

        # Add each suffix.
        for i in range(len(string_extended)):
            self._add_prefix(i, string_extended, string_id)

    def _add_prefix(self, i, string, string_id):
        """The core construction method.
        """
        last_parent_node = None
        parent_node_id = None
        while True:
            parent_node_id = self.suffix.source_node_id

            # Break if prefix is already in tree.
            if self.suffix.explicit():
                # Explicit suffix points to an existing node. Try to find the node.
                prefix = string[i]
                try:
                    e = self.get_edge(make_edge_id(self.suffix.source_node_id, prefix))
                except KeyError:
                    # If the edge doesn't exist, the prefix isn't in the
                    # tree, so continue by adding an edge and a node.
                    pass
                else:
                    # Although, in case it's a leaf node that remains because
                    # an earlier suffix of string ID was removed, and so
                    # doesn't have a 'string_id' value, then set 'string_id' now.
                    dest_node = self.get_node(e.dest_node_id)
                    if self.is_leaf(dest_node) and dest_node.string_id is None:
                        dest_node.string_id = string_id

                        # Adjust the active suffix.
                        self.move_suffix_along_by_one(string)

                    # The edge was found, so exit the loop.
                    break

            else:
                # Break if prefix is already in tree.
                prefix = string[self.suffix.first_char_index]
                e = self.get_edge(make_edge_id(self.suffix.source_node_id, prefix))
                if e.label[self.suffix.length + 1] == string[i]:

                    # The suffix was found in this edge, so exit the loop.
                    break

                # Split the edge, with a new middle node that will be the parent node.
                parent_node_id = self._split_edge(e, self.suffix, string_id)

            # Otherwise the prefix isn't in the tree, so create an edge and node for this prefix.
            node = register_new_node(string_id=string_id)
            self._cache_node(node)


            # Make a new edge from the parent node to the
            # new leaf node. Make a label for the edge to
            # the leaf, using the suffix of the string
            # from i onwards.
            e = register_new_edge(
                edge_id=make_edge_id(parent_node_id, string[i]),
                label=string[i:],
                source_node_id=parent_node_id,
                dest_node_id=node.id,
            )

            # Register the new leaf node as a child node of the parent node.
            parent_node = self.get_node(parent_node_id)
            # - also pass in the number of chars, used when finding strings
            parent_node.add_child_node_id(node.id, e.length + 1)
            self._cache_edge(e)

            # Unless parent is root, set the last parent's suffix
            # node ID as the current parent node ID.
            if last_parent_node is not None:
                assert isinstance(last_parent_node, SuffixTreeNode)
                last_parent_node.suffix_node_id = parent_node_id

            # Remember the last parent node.
            last_parent_node = parent_node

            # Adjust the active suffix.
            self.move_suffix_along_by_one(string)

        # Create suffix link from last parent to current parent.
        if last_parent_node is not None:
            assert parent_node_id is not None
            last_parent_node.suffix_node_id = parent_node_id


        self.suffix.last_char_index += 1
        self._canonize_suffix(self.suffix, string)

    def move_suffix_along_by_one(self, string):
        # Move the suffix along by one.
        if self.suffix.source_node_id == self.root_node_id:
            self.suffix.first_char_index += 1
        else:
            self.suffix.source_node_id = self.get_node(self.suffix.source_node_id).suffix_node_id
        self._canonize_suffix(self.suffix, string)

    def is_leaf(self, dest_node):
        return self.is_inner_node(dest_node) and not self.is_root_node(dest_node)

    def is_root_node(self, dest_node):
        return dest_node.id == self.root_node_id

    def is_inner_node(self, dest_node):
        return dest_node.suffix_node_id is None

    def remove_string(self, string, string_id):
        assert isinstance(string_id, six.string_types)
        if self._case_insensitive:
            string = string.lower()
        assert STRING_ID_END not in string_id
        assert STRING_ID_END not in string
        string += u"{}{}".format(string_id, STRING_ID_END)
        for i in range(len(string)):

            # Walk down the tree.
            suffix = Suffix(self.root_node_id, i, len(string) - 1)
            self._canonize_suffix(suffix, string)

            # Get the leaf node.
            leaf_node = self.get_node(suffix.source_node_id)
            assert isinstance(leaf_node, SuffixTreeNode)

            # Disassociate the string ID from the leaf node.
            #  - but don't discard the node entity, because we might
            #    need to add this suffix back into the tree,
            #    and pruning hard would be relatively complicated
            #  - it would be possible separately to either rebuild
            #    the tree, or garbage collect leaf nodes
            if leaf_node.string_id == string_id:
                leaf_node.string_id = None

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
        # Todo: Change this (and callers) to return (and handle) None when the edge is not found.
        """

        :rtype: SuffixTreeNode
        """
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

    def _split_edge(self, first_edge, suffix, string_id):
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

    class Created(EventSourcedEntity.Created):
        pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged):
        pass

    class Discarded(EventSourcedEntity.Discarded):
        pass

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
        """
        :type source_node_id: six.string_types
            Index of node where this suffix starts.

        :type first_char_index: six.string_types
            Index of start of suffix in string.

        :type last_char_index: six.string_types
            Index of end of suffix in string.
        """
        assert isinstance(source_node_id, six.string_types)
        assert isinstance(first_char_index, six.integer_types)
        assert isinstance(last_char_index, six.integer_types)
        assert source_node_id is not None
        self.source_node_id = source_node_id
        self.first_char_index = first_char_index
        self.last_char_index = last_char_index

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
    suffix_tree_id = uuid4().hex

    root_node = register_new_node()

    event = GeneralizedSuffixTree.Created(
        entity_id=suffix_tree_id,
        root_node_id=root_node.id,
        case_insensitive=case_insensitive,
    )
    entity = GeneralizedSuffixTree.mutate(event=event)

    assert isinstance(entity, GeneralizedSuffixTree)

    entity.nodes[root_node.id] = root_node

    publish(event)

    if string is not None:
        assert string_id
        entity.add_string(string, string_id)

    return entity


# Repositories.

class GeneralizedSuffixTreeRepository(EntityRepository):
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
    assert isinstance(suffix_tree, GeneralizedSuffixTree)
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


# Todo: Move this to a separate package called 'suffixtrees'


def get_leaf_nodes(node_id, node_repo, length_until_end=0, edge_length=0, limit=None,
                   hop_count=0, hop_max=300):
    """Generator that performs a depth first search on the suffix tree from the given node,
    yielding unique string IDs as they are discovered.
    """
    if hop_count >= hop_max:
        raise StopIteration
    hop_count += 1

    stack = list()

    stack.append((node_id, edge_length, None))
    unique_string_ids = set()
    cum_lengths_until_end = {None: length_until_end}
    while stack:

        (node_id, edge_length, parent_node_id) = stack.pop()

        length_until_end = cum_lengths_until_end[parent_node_id] + edge_length
        cum_lengths_until_end[node_id] = length_until_end

        node = node_repo[node_id]
        assert isinstance(node, SuffixTreeNode)

        if not node._child_node_ids:

            # If a string has been removed, leaf nodes will have None as the value of string_id.
            if node.string_id is None:
                continue

            # Deduplicate string IDs (the substring might match more than one suffix in any given string).
            if node.string_id in unique_string_ids:
                continue

            # Check the match doesn't encroach upon the string's extension.
            extension_length = len(node.string_id) + len(STRING_ID_END)
            if length_until_end < extension_length:
                continue

            # Remember the string ID, we only want one node per string ID.
            unique_string_ids.add(node.string_id)

            # Yield the node.
            yield node

            # Check if the limit has been reached.
            if limit is not None and len(unique_string_ids) >= limit:
                raise StopIteration

        # Otherwise it's a node with children, so put then on the stack.
        else:
            for (child_node_id, edge_length) in node._child_node_ids.items():
                stack.append((child_node_id, edge_length, node.id))
