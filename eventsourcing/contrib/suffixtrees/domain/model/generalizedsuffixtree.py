# coding=utf-8
from __future__ import unicode_literals

from collections import OrderedDict
from uuid import uuid4

import six
from singledispatch import singledispatch

from eventsourcing.domain.model.entity import EventSourcedEntity, mutableproperty, EntityRepository, entity_mutator
from eventsourcing.domain.model.events import publish, DomainEvent
from eventsourcing.exceptions import ConcurrencyError, RepositoryKeyError

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
        self._string = None
        self._suffix = None
        self._node_repo = None
        self._node_child_collection_repo = None
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
            retries = 5
            while True:
                retries -= 1
                try:
                    self._add_prefix(i, string_extended, string_id)
                except ConcurrencyError:
                    if retries <= 0:
                        raise
                else:
                    break

    def _add_prefix(self, i, string, string_id):
        """The core construction method.
        """
        last_parent_node_id = None
        parent_node_id = None
        while True:
            parent_node_id = self.suffix.source_node_id

            # Break if prefix is already in tree.
            if self.suffix.explicit():
                # Explicit suffix points to an existing node. Try to find the node.
                prefix = string[i]
                try:
                    edge = self.get_edge(make_edge_id(self.suffix.source_node_id, prefix))
                except KeyError:
                    # If the edge doesn't exist, the prefix isn't in the
                    # tree, so continue by adding an edge and a node.
                    pass
                else:
                    # Although, if edge destination is a leaf node that doesn't have
                    # a 'string_id' value (because an earlier suffix of string ID
                    # was removed), then set its 'string_id' attribute now.
                    dest_node = self.get_node(edge.dest_node_id)
                    if self.is_leaf(dest_node) and dest_node.string_id is None:
                        dest_node.string_id = string_id

                        # Adjust the active suffix.
                        self.move_suffix_along_by_one(string)

                    # The edge was found, so exit the loop.
                    break

            else:
                # Break if prefix is already in tree.
                prefix = string[self.suffix.first_char_index]
                edge = self.get_edge(make_edge_id(self.suffix.source_node_id, prefix))
                if edge.label[self.suffix.length + 1] == string[i]:

                    # The suffix was found in this edge, so exit the loop.
                    break

                # Split the edge, with a new middle node that will be the parent node.
                parent_node_id = self._split_edge(edge, self.suffix)

            # Otherwise the prefix isn't in the tree, so create an edge and node for this prefix.
            new_node = register_new_node(string_id=string_id)
            self._cache_node(new_node)

            # Make a new edge from the parent node to the
            # new leaf node. Make a label for the edge to
            # the leaf, using the suffix of the string
            # from i onwards.
            new_edge = register_new_edge(
                edge_id=make_edge_id(parent_node_id, string[i]),
                label=string[i:],
                source_node_id=parent_node_id,
                dest_node_id=new_node.id,
            )

            # Register the new leaf node as a child node of the parent node.
            parent_node_child_collection = self.get_node_child_collection(parent_node_id)
            # - also pass in the number of chars (used when finding strings)
            parent_node_child_collection.add_child(new_node.id, new_edge.length + 1)

            # Create suffix link from last parent to current parent (unless it's root).
            self.create_suffix_link(last_parent_node_id, parent_node_id)

            # Remember the last parent node.
            last_parent_node_id = parent_node_id

            # Adjust the active suffix.
            self.move_suffix_along_by_one(string)

        # Create suffix link from last parent to current parent (unless it's root).
        self.create_suffix_link(last_parent_node_id, parent_node_id)

        self.suffix.last_char_index += 1
        self._canonize_suffix(self.suffix, string)

    def _split_edge(self, first_edge, suffix):
        assert isinstance(first_edge, SuffixTreeEdge)
        assert isinstance(suffix, Suffix)

        # Split the label.
        first_label = first_edge.label[:suffix.length + 1]
        second_label = first_edge.label[suffix.length + 1:]

        # Create a new middle node that will split the edge.
        new_middle_node = register_new_node(suffix_node_id=suffix.source_node_id)
        self._cache_node(new_middle_node)

        # Create a new edge, from the new middle node to the original destination.
        second_edge_id = make_edge_id(source_node_id=new_middle_node.id, first_char=second_label[0])
        original_dest_node_id = first_edge.dest_node_id
        second_edge = register_new_edge(
            label=second_label,
            edge_id=second_edge_id,
            source_node_id=new_middle_node.id,
            dest_node_id=original_dest_node_id,
        )

        # Add the original dest node as a child of the new middle node.
        new_middle_node_child_collection = self.get_node_child_collection(new_middle_node.id)
        new_middle_node_child_collection.add_child(original_dest_node_id, second_edge.length + 1)

        # Shorten the first edge (last so that everything above is in place).
        try:
            first_edge.shorten(label=first_label, dest_node_id=new_middle_node.id)
        except ConcurrencyError:
            # If the first edge has changed by now, then abort this split by
            # discarding the new_middle_node and the second_edge, which haven't
            # been connected to the tree yet, so can safely be discarded.
            new_middle_node.discard()
            second_edge.discard()
            raise

        # Remove the original dest node as child of the original
        # source node, and add the new middle node instead.
        original_source_node_child_collection = self.get_node_child_collection(first_edge.source_node_id)
        assert isinstance(original_source_node_child_collection, SuffixTreeNodeChildCollection)
        original_source_node_child_collection.switch_child(original_dest_node_id, new_middle_node.id, first_edge.length + 1)

        # Return middle node.
        return new_middle_node.id

    def create_suffix_link(self, last_parent_node_id, parent_node_id):
        if last_parent_node_id is not None:
            assert parent_node_id is not None
            last_parent_node = self.get_node(last_parent_node_id)
            assert isinstance(last_parent_node, SuffixTreeNode)
            last_parent_node.suffix_node_id = parent_node_id

    def move_suffix_along_by_one(self, string):
        # Move the suffix along by one.
        if self.suffix.source_node_id == self.root_node_id:
            self.suffix.first_char_index += 1
        else:
            self.suffix.source_node_id = self.get_node(self.suffix.source_node_id).suffix_node_id
        self._canonize_suffix(self.suffix, string)

    def is_leaf(self, dest_node):
        return not self.is_inner_node(dest_node) and not self.is_root_node(dest_node)

    def is_root_node(self, dest_node):
        return dest_node.id == self.root_node_id

    def is_inner_node(self, dest_node):
        return dest_node.suffix_node_id is not None

    def remove_string(self, string, string_id):
        assert isinstance(string_id, six.string_types)
        if self._case_insensitive:
            string = string.lower()
        assert STRING_ID_END not in string_id
        assert STRING_ID_END not in string
        string += u"{}{}".format(string_id, STRING_ID_END)
        # Disassociate the string ID from its leaf nodes.
        #  - but don't discard the node entity, because we might
        #    need to add this suffix back into the tree,
        #    and a hard prune would be relatively complicated.
        #  - although, it might be useful to have something do garbage collection
        for i in range(len(string)):

            # Walk down the tree.
            suffix = Suffix(self.root_node_id, i, len(string) - 1)
            self._canonize_suffix(suffix, string)

            # Get the leaf node.
            leaf_node = self.get_node(suffix.source_node_id)
            assert isinstance(leaf_node, SuffixTreeNode)
            if leaf_node.string_id == string_id:
                leaf_node.string_id = None

    def get_edge(self, edge_id):
        # Raises KeyError is not found because this method was factored out from various places that
        # used the repo directly and so expected a KeyError to be raised if edge is not in repo.
        return self._edge_repo[edge_id]

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
            except RepositoryKeyError:
                raise e
            else:
                self._cache_node(node)
                return node

    def _cache_node(self, node):
        self.nodes[node.id] = node

    def get_node_child_collection(self, node_id):
        """
        Returns children of node.

        :rtype: SuffixTreeNodeChildren
        """
        try:
            node = self._node_child_collection_repo[node_id]
        except RepositoryKeyError:
            node = register_new_node_child_collection(node_id)
        return node

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

    def __init__(self, suffix_node_id=None, string_id=None, *args, **kwargs):
        super(SuffixTreeNode, self).__init__(*args, **kwargs)
        self.suffix_node_id = suffix_node_id
        self._string_id = string_id

    @mutableproperty
    def string_id(self):
        """The id of a string being added to the generalised suffix tree when this node was created.
        """

    def __repr__(self):
        return "SuffixTreeNode(suffix link: {})".format(self.suffix_node_id)


class SuffixTreeNodeChildCollection(EventSourcedEntity):
    """A collecton of child nodes in the suffix tree.
    """

    class Created(EventSourcedEntity.Created): pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged): pass

    class Discarded(EventSourcedEntity.Discarded): pass

    class ChildNodeAdded(DomainEvent): pass

    class ChildNodeRemoved(DomainEvent): pass

    class ChildNodeSwitched(DomainEvent): pass

    def __init__(self, *args, **kwargs):
        super(SuffixTreeNodeChildCollection, self).__init__(*args, **kwargs)
        self._child_node_ids = OrderedDict()

    @mutableproperty
    def string_id(self):
        """The id of a string being added to the generalised suffix tree when this node was created.
        """

    def add_child(self, child_node_id, edge_len):
        event = SuffixTreeNodeChildCollection.ChildNodeAdded(
            entity_id=self.id,
            entity_version=self.version,
            child_node_id=child_node_id,
            edge_len=edge_len,
        )
        self._apply(event)
        publish(event)

    def switch_child(self, old_node_id, new_node_id, new_edge_len):
        event = SuffixTreeNodeChildCollection.ChildNodeSwitched(
            entity_id=self.id,
            entity_version=self.version,
            old_node_id=old_node_id,
            new_node_id=new_node_id,
            new_edge_len=new_edge_len,
        )
        self._apply(event)
        publish(event)

    @staticmethod
    def _mutator(event, initial):
        return suffix_tree_node_child_collection_mutator(event, initial)


@singledispatch
def suffix_tree_node_child_collection_mutator(event, initial):
    return entity_mutator(event, initial)


@suffix_tree_node_child_collection_mutator.register(SuffixTreeNodeChildCollection.ChildNodeAdded)
def child_node_child_collection_added_mutator(event, self):
    assert isinstance(self, SuffixTreeNodeChildCollection), self
    self._child_node_ids[event.child_node_id] = event.edge_len
    self._increment_version()
    return self


@suffix_tree_node_child_collection_mutator.register(SuffixTreeNodeChildCollection.ChildNodeSwitched)
def child_node_child_collection_switched_mutator(event, self):
    assert isinstance(self, SuffixTreeNodeChildCollection), self
    try:
        del(self._child_node_ids[event.old_node_id])
    except KeyError:
        pass
    self._child_node_ids[event.new_node_id] = event.new_edge_len
    self._increment_version()
    return self


class SuffixTreeEdge(EventSourcedEntity):
    """An edge in the suffix tree.
    """

    class Created(EventSourcedEntity.Created):
        pass

    class AttributeChanged(EventSourcedEntity.AttributeChanged):
        pass

    class Shortened(DomainEvent):
        @property
        def label(self):
            return self.__dict__['label']

        @property
        def dest_node_id(self):
            return self.__dict__['dest_node_id']

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

    def shorten(self, label, dest_node_id):
        self._assert_not_discarded()
        event = SuffixTreeEdge.Shortened(
            entity_id=self._id,
            entity_version=self._version,
            label=label,
            dest_node_id=dest_node_id,
        )
        self._apply(event)
        publish(event)

    @staticmethod
    def _mutator(event, initial):
        return suffix_tree_edge_mutator(event, initial)


@singledispatch
def suffix_tree_edge_mutator(event, initial):
    return entity_mutator(event, initial)


@suffix_tree_edge_mutator.register(SuffixTreeEdge.Shortened)
def suffix_tree_edge_shortened_mutator(event, self):
    assert isinstance(event, SuffixTreeEdge.Shortened), event
    assert isinstance(self, SuffixTreeEdge), type(self)
    self._validate_originator(event)
    self._label = event.label
    self._dest_node_id = event.dest_node_id
    self._increment_version()
    return self


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


def register_new_node_child_collection(node_id):
    """Factory method, registers new node child collection.
    """
    event = SuffixTreeNodeChildCollection.Created(
        entity_id=node_id,
    )
    entity = SuffixTreeNodeChildCollection.mutate(event=event)
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


def register_new_suffix_tree(case_insensitive=False):
    """Factory method, returns new suffix tree object.
    """
    assert isinstance(case_insensitive, bool)

    suffix_tree_id = uuid4().hex

    root_node = register_new_node()
    assert isinstance(root_node, SuffixTreeNode)
    # root_node.suffix_node_id = root_node.id

    event = GeneralizedSuffixTree.Created(
        entity_id=suffix_tree_id,
        root_node_id=root_node.id,
        case_insensitive=case_insensitive,
    )
    entity = GeneralizedSuffixTree.mutate(event=event)

    assert isinstance(entity, GeneralizedSuffixTree)

    entity.nodes[root_node.id] = root_node

    publish(event)

    return entity


# Repositories.

class GeneralizedSuffixTreeRepository(EntityRepository):
    pass


class NodeRepository(EntityRepository):
    pass


class EdgeRepository(EntityRepository):
    pass
