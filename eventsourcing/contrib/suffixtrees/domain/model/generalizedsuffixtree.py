# # coding=utf-8
# from __future__ import unicode_literals
#
# from collections import OrderedDict
# from time import sleep
# from uuid import uuid4
#
# from eventsourcing.domain.model.collection import Collection
# from eventsourcing.domain.model.entity import AbstractEntityRepository, AttributeChanged, Created, Discarded, \
#     TimestampedVersionedEntity, attribute, mutate_entity
# from eventsourcing.domain.model.events import TimestampedVersionedEntityEvent, publish, mutator
# from eventsourcing.exceptions import ConcurrencyError, RepositoryKeyError
#
# # Use a private code point to terminate the strings.
# STRING_ID_END = '\uEFFF'
#
#
# class GeneralizedSuffixTree(TimestampedVersionedEntity):
#     """A suffix tree for string matching. Uses Ukkonen's algorithm
#     for construction.
#
#     Adding strings to individual suffix trees needs to be serialized,
#     so you need to use locks around calls to add_string() in a
#     distributed application.
#     """
#
#     class Created(Created):
#         pass
#
#     class AttributeChanged(AttributeChanged):
#         pass
#
#     class Discarded(Discarded):
#         pass
#
#     def __init__(self, root_node_id, case_insensitive=False, **kwargs):
#         super(GeneralizedSuffixTree, self).__init__(**kwargs)
#         self._root_node_id = root_node_id
#         self._case_insensitive = case_insensitive
#         # self._nodes = {}
#         self._string = None
#         self._suffix = None
#         self._node_repo = None
#         self._node_child_collection_repo = None
#         self._edge_repo = None
#         self._stringid_collection_repo = None
#
#     @attribute
#     def string(self):
#         return self._string
#
#     @property
#     def nodes(self):
#         return self._nodes
#
#     @property
#     def root_node_id(self):
#         return self._root_node_id
#
#     @property
#     def suffix(self):
#         return self._suffix
#
#     @property
#     def case_insensitive(self):
#         return self._case_insensitive
#
#     def __repr__(self):
#         """
#         Lists edges in the suffix tree
#         """
#         # Todo: Something that shows the actual tree.
#         return ('GeneralizedSuffixTree(id={0.id}, root_node_id={0.root_node_id}, case_insensitive={'
#                 '0.case_insensitive})'.format(self))
#
#     def add_string(self, string, string_id):
#         assert isinstance(string, str)
#         assert isinstance(string_id, str)
#
#         # Lower the string, if it's a case insensitive tree.
#         if self._case_insensitive:
#             string = string.lower()
#         assert STRING_ID_END not in string_id
#         assert STRING_ID_END not in string
#
#         # Append the (hopefully unique) string ID to the string.
#         string_extended = u"{}{}".format(string, STRING_ID_END)
#
#         self._suffix = Suffix(self._root_node_id, 0, -1)
#         for i in range(len(string_extended)):
#             self._add_prefix(i, string_extended, string_id)
#
#     def _add_prefix(self, i, string, string_id):
#         """The core construction method.
#         """
#         last_parent_node_id = None
#         parent_node_id = None
#         added_node_ids = set()
#         while True:
#
#             parent_node_id = self.suffix.source_node_id
#
#             # Break if prefix is already in tree.
#             if self.suffix.explicit():
#                 # Explicit suffix points to an existing node. Try to find the node.
#                 prefix = string[i]
#                 try:
#                     edge = self.get_edge(make_edge_id(parent_node_id, prefix))
#                 except KeyError:
#                     # If the edge doesn't exist, the prefix isn't in the
#                     # tree, so continue by adding an edge and a node.
#                     # print("Explicit suffix, edge not found for letter '{}'".format(prefix))
#                     pass
#                 else:
#                     # The edge was found, so exit the loop.
#                     # print("Explicit suffix, edge found for letter '{}': {}".format(prefix, edge))
#
#                     # Although, might need to add string ID to node collection, if it's a leaf and exact match.
#                     dest_node = self.get_node(edge.dest_node_id)
#                     if self.is_leaf(dest_node):
#
#                         # If it's an exact match...
#                         if edge.label == string[i:]:
#
#                             # Add the string ID to the node collection.
#                             self.add_string_id(edge.dest_node_id, string_id)
#                             # print("Added string ID '{}' to explicit exact match {}".format(string_id, dest_node))
#
#                             # Attempt to replicate for a duplicate what happens first time a string was added.
#                             if edge.dest_node_id not in added_node_ids:
#                                 # Adjust the active suffix.
#                                 self.follow_suffix_link_or_increment_suffix_first_char(string)
#
#                     break
#
#             else:
#                 # Break if prefix is already in tree.
#                 prefix = string[self.suffix.first_char_index]
#                 edge = self.get_edge(make_edge_id(self.suffix.source_node_id, prefix))
#                 suffix_label_offset = self.suffix.length + 1
#                 if suffix_label_offset > len(edge.label) - 1:
#                     raise ValueError(
#                         "Suffix offset too large for label: %s: %s" % (suffix_label_offset, edge.label[:100]))
#                 # print("Implicit edge dest node: {}".format(edge.dest_node_id))
#                 if edge.label[suffix_label_offset] == string[i]:
#                     # print("Matched edge label til end of suffix: {} {}".format(edge.label[:100],
#                     # suffix_label_offset))
#                     # The suffix was found in this edge, so exit the loop.
#
#                     # Add the string ID to the node collection.
#                     self.add_string_id(edge.dest_node_id, string_id)
#                     # print("Added string ID '{}' to implicit exact match: {}".format(string_id, self.get_node(
#                     # edge.dest_node_id)))
#
#                     break
#
#                 else:
#                     # Split the edge, with a new middle node that will be the parent node.
#                     parent_node_id = self._split_edge(edge, self.suffix)
#
#             # Otherwise the prefix isn't in the tree, so create a node and an edge for this prefix.
#             new_leaf_node = register_new_node(string_id=string_id, is_leaf=True)
#
#             # Remeber this node was created in this call.
#             added_node_ids.add(new_leaf_node.id)
#
#             # Make a new edge from the parent node to the
#             # new leaf node. Make a label for the edge to
#             # the leaf, using the suffix of the string
#             # from i onwards.
#             new_edge = register_new_edge(
#                 edge_id=make_edge_id(parent_node_id, string[i]),
#                 label=string[i:],
#                 source_node_id=parent_node_id,
#                 dest_node_id=new_leaf_node.id,
#             )
#
#             # print("For letter '{}' added node and edge: {}".format(string[i], new_edge))
#
#             # Add the new leaf node as a child node of the parent node.
#             self.add_child_node(parent_node_id, new_leaf_node.id, new_edge.length + 1)
#
#             # Add the string ID to the node collection.
#             self.add_string_id(new_leaf_node.id, string_id)
#             # print("Added string ID '{}' to new node {}".format(string_id, new_leaf_node))
#
#             # Create suffix link from last parent to current parent (unless it's root).
#             self.create_suffix_link(last_parent_node_id, parent_node_id)
#
#             # Remember the last parent node.
#             last_parent_node_id = parent_node_id
#
#             # Adjust the active suffix.
#             self.follow_suffix_link_or_increment_suffix_first_char(string)
#
#         # Create suffix link from last parent to current parent (unless it's root).
#         self.create_suffix_link(last_parent_node_id, parent_node_id)
#
#         # Which is the last leaf node?
#
#         self.suffix.last_char_index += 1
#         # print("Incremented suffix last char index: {}".format(self.suffix.last_char_index))
#
#         self._canonize_suffix(self.suffix, string)
#         # print("Cannonized suffix: {}".format(self.suffix))
#
#     def _split_edge(self, first_edge, suffix):
#         assert isinstance(first_edge, SuffixTreeEdge)
#         assert isinstance(suffix, Suffix)
#
#         # Split the label.
#         orig_label = first_edge.label
#         first_label = orig_label[:suffix.length + 1]
#         second_label = orig_label[suffix.length + 1:]
#
#         # print("Splitting edge: {}  <==>  {}".format(first_label[:100], second_label[:100]))
#
#         # Create a new middle node that will split the edge.
#         new_middle_node = register_new_node(suffix_node_id=suffix.source_node_id)
#         # self._cache_node(new_middle_node)
#
#         # print("New middle node: {}".format(new_middle_node))
#
#         # Create a new edge, from the new middle node to the original destination.
#         second_edge_id = make_edge_id(source_node_id=new_middle_node.id, first_char=second_label[0])
#         original_dest_node_id = first_edge.dest_node_id
#
#         second_edge = register_new_edge(
#             label=second_label,
#             edge_id=second_edge_id,
#             source_node_id=new_middle_node.id,
#             dest_node_id=original_dest_node_id,
#         )
#
#         # print("New second edge: {}".format(second_edge))
#
#         # Add the original dest node as a child of the new middle node.
#         self.add_child_node(
#             parent_node_id=new_middle_node.id,
#             child_node_id=original_dest_node_id,
#             edge_length=second_edge.length + 1,
#         )
#
#         # Shorten the first edge, so its destination is the new middle node.
#         try:
#             first_edge.shorten(label=first_label, dest_node_id=new_middle_node.id)
#             # print("Shortened first edge: {}".format(first_edge))
#         except ConcurrencyError as e:
#             # If the first edge has changed by now, then abort this split by
#             # discarding the new_middle_node, which hasn't been connected to
#             # the tree yet, so can safely be discarded.
#             new_middle_node.discard()
#             sleep(0.1)
#             raise e
#
#         # Remove the original dest node as child of the original
#         # source node, and add the new middle node instead.
#         self.switch_child_node(
#             parent_node_id=first_edge.source_node_id,
#             old_child_id=original_dest_node_id,
#             new_child_id=new_middle_node.id,
#             edge_length=first_edge.length + 1,
#         )
#
#         # Return middle node.
#         return new_middle_node.id
#
#     def add_child_node(self, parent_node_id, child_node_id, edge_length):
#         collection = self.get_or_create_node_child_collection(parent_node_id)
#         if child_node_id not in collection.child_node_ids:
#             # - also pass in the edge length (used when finding strings)
#             collection.add_child(child_node_id, edge_length)
#
#     def switch_child_node(self, parent_node_id, old_child_id, new_child_id, edge_length):
#         collection = self.get_or_create_node_child_collection(parent_node_id)
#         assert isinstance(collection, SuffixTreeNodeChildCollection)
#         collection.switch_child(old_child_id, new_child_id, edge_length)
#
#     def add_string_id(self, parent_node_id, string_id):
#         collection = self.get_or_create_stringid_collection(parent_node_id)
#         if string_id not in collection.items:
#             collection.add_item(string_id)
#
#     def create_suffix_link(self, last_parent_node_id, parent_node_id):
#         if last_parent_node_id is not None:
#             assert parent_node_id is not None
#
#             # Set suffix_node_id on last_parent_node to parent_node_id.
#             last_parent_node = self.get_node(last_parent_node_id)
#             assert isinstance(last_parent_node, SuffixTreeNode)
#             last_parent_node.suffix_node_id = parent_node_id
#
#     def follow_suffix_link_or_increment_suffix_first_char(self, string):
#         # If we're at root, there isn't a suffix link, so increment the first char index.
#         if self.suffix.source_node_id == self.root_node_id:
#             # print("Incrementing suffix first char...")
#             self.suffix.first_char_index += 1
#         else:
#             # If we're not at root, follow the suffix link.
#             last_source_node_id = self.suffix.source_node_id
#             next_source_node_id = self.get_node(last_source_node_id).suffix_node_id
#             # print("Following suffix link from {} to {}".format(last_source_node_id, next_source_node_id))
#             self.suffix.source_node_id = next_source_node_id
#         self._canonize_suffix(self.suffix, string)
#
#     def is_leaf(self, dest_node):
#         return dest_node.is_leaf
#
#     def is_root_node(self, dest_node):
#         return dest_node.is_root
#
#     def remove_string(self, string, string_id):
#         # Todo: Maybe this is an application service?
#
#         assert isinstance(string_id, str)
#         if self._case_insensitive:
#             string = string.lower()
#         assert STRING_ID_END not in string_id
#         assert STRING_ID_END not in string
#         # string += u"{}{}".format(string_id, STRING_ID_END)
#         string += u"{}".format(STRING_ID_END)
#
#         # Disassociate the string ID from its leaf nodes.
#         #  - but don't discard the node entity, because we might
#         #    need to add this suffix back into the tree,
#         #    and a hard prune would be relatively complicated.
#         #  - although, it might be useful to have something do garbage collection
#         from eventsourcing.contrib.suffixtrees.domain.services.generalizedsuffixtree import find_substring_edge
#
#         for i in range(len(string)):
#
#             # Find the suffix in the tree.
#
#             suffix = string[i:]
#             edge, ln = find_substring_edge(suffix, self, self._edge_repo)
#
#             if edge is None:
#                 continue
#
#             # Get the leaf node.
#             leaf_node = self.get_node(edge.dest_node_id)
#             assert isinstance(leaf_node, SuffixTreeNode)
#             if leaf_node.string_id == string_id:
#                 leaf_node.string_id = None
#             try:
#                 stringid_collection = self._stringid_collection_repo[leaf_node.id]
#             except KeyError:
#                 pass
#             else:
#                 assert isinstance(stringid_collection, StringidCollection)
#                 if string_id in stringid_collection.items:
#                     stringid_collection.remove_item(string_id)
#
#     def get_edge(self, edge_id):
#         # Raises KeyError is not found because this method was factored out from various places that
#         # used the repo directly and so expected a KeyError to be raised if edge is not in repo.
#         return self._edge_repo[edge_id]
#
#     def has_edge(self, edge_id):
#         try:
#             return self.get_edge(edge_id)
#         except KeyError:
#             pass
#
#     def get_node(self, node_id):
#         # Raises KeyError is not found because this method was factored out from various places that
#         # used the repo directly and so expected a KeyError to be raised if node is not in repo.
#         # Todo: Change this (and callers) to return (and handle) None when the edge is not found.
#         """
#
#         :rtype: SuffixTreeNode
#         """
#         # if not self._node_repo:
#         #     return self.nodes[node_id]
#         # try:
#         #     return self.nodes[node_id]
#         # except KeyError as e:
#         #     try:
#         #         node = self._node_repo[node_id]
#         #     except KeyError:
#         #         raise e
#         #     else:
#         #         self._cache_node(node)
#         #         return node
#
#         return self._node_repo[node_id]
#
#     def _cache_node(self, node):
#         self.nodes[node.id] = node
#
#     def get_or_create_node_child_collection(self, node_id):
#         """
#         Returns children of node.
#
#         :rtype: SuffixTreeNodeChildCollection
#         """
#         try:
#             node = self._node_child_collection_repo[node_id]
#         except RepositoryKeyError:
#             node = register_new_node_child_collection(node_id)
#         return node
#
#     def get_or_create_stringid_collection(self, node_id):
#         """
#         Returns collection of string IDs.
#
#         :rtype: StringidCollection
#         """
#         try:
#             node = self._stringid_collection_repo[node_id]
#         except KeyError:
#             node = register_new_stringid_collection(node_id)
#         return node
#
#     def _canonize_suffix(self, suffix, string):
#         """This canonizes the suffix, walking along its suffix string until it
#         is explicit or there are no more matched nodes.
#         """
#         if not suffix.explicit():
#             if len(string) < suffix.first_char_index + 1:
#                 raise AssertionError("String length is {} and suffix first char index is {}"
#                                      "".format(len(string), suffix.first_char_index))
#             edge_id = make_edge_id(suffix.source_node_id, string[suffix.first_char_index])
#             e = self.get_edge(edge_id)
#             if e.length <= suffix.length:
#                 suffix.first_char_index += e.length + 1
#                 suffix.source_node_id = e.dest_node_id
#                 self._canonize_suffix(suffix, string)
#
#
# class SuffixTreeNode(TimestampedVersionedEntity):
#     """A node in the suffix tree.
#     """
#
#     class Created(Created): pass
#
#     class AttributeChanged(AttributeChanged): pass
#
#     class Discarded(Discarded): pass
#
#     def __init__(self, suffix_node_id=None, string_id=None, is_leaf=False, is_root=False, *args, **kwargs):
#         super(SuffixTreeNode, self).__init__(*args, **kwargs)
#         self._suffix_node_id = suffix_node_id
#         self._string_id = string_id
#         self._is_leaf = is_leaf
#         self._is_root = is_root
#
#     @attribute
#     def string_id(self):
#         """The id of a string being added to the generalised suffix tree when this node was created.
#         """
#
#     @attribute
#     def suffix_node_id(self):
#         """The ID of the node representing the suffix of the suffix represented by this node.
#         """
#
#     @property
#     def is_leaf(self):
#         return self._is_leaf
#
#     @property
#     def is_root(self):
#         return self._is_root
#
#     def __repr__(self):
#         return "Node(id='{}')".format(self.id)
#
#
# class StringidCollection(Collection):
#     class Created(Collection.Created):
#         pass
#
#     class ItemAdded(Collection.ItemAdded):
#         pass
#
#     class ItemRemoved(Collection.ItemRemoved):
#         pass
#
#
# class SuffixTreeNodeChildCollection(TimestampedVersionedEntity):
#     """A collecton of child nodes in the suffix tree.
#     """
#
#     class Created(Created): pass
#
#     class AttributeChanged(AttributeChanged): pass
#
#     class Discarded(Discarded): pass
#
#     class ChildNodeAdded(TimestampedVersionedEntityEvent): pass
#
#     class ChildNodeRemoved(TimestampedVersionedEntityEvent): pass
#
#     class ChildNodeSwitched(TimestampedVersionedEntityEvent): pass
#
#     def __init__(self, *args, **kwargs):
#         super(SuffixTreeNodeChildCollection, self).__init__(*args, **kwargs)
#         self._child_node_ids = OrderedDict()
#
#     @property
#     def child_node_ids(self):
#         return self._child_node_ids
#
#     def add_child(self, child_node_id, edge_len):
#         event = SuffixTreeNodeChildCollection.ChildNodeAdded(
#             originator_id=self.id,
#             originator_version=self.__version__,
#             child_node_id=child_node_id,
#             edge_len=edge_len,
#         )
#         self._apply(event)
#         publish(event)
#
#     def switch_child(self, old_node_id, new_node_id, new_edge_len):
#         event = SuffixTreeNodeChildCollection.ChildNodeSwitched(
#             originator_id=self.id,
#             originator_version=self.__version__,
#             old_node_id=old_node_id,
#             new_node_id=new_node_id,
#             new_edge_len=new_edge_len,
#         )
#         self._apply(event)
#         publish(event)
#
#     @staticmethod
#     def _mutator(initial, event):
#         return suffix_tree_node_child_collection_mutator(initial, event)
#
#
# @mutator
# def suffix_tree_node_child_collection_mutator(initial, event):
#     return mutate_entity(initial, event)
#
#
# @suffix_tree_node_child_collection_mutator.register(SuffixTreeNodeChildCollection.ChildNodeAdded)
# def child_node_child_collection_added_mutator(self, event):
#     assert isinstance(self, SuffixTreeNodeChildCollection), self
#     self._child_node_ids[event.child_node_id] = event.edge_len
#     self._increment_version()
#     return self
#
#
# @suffix_tree_node_child_collection_mutator.register(SuffixTreeNodeChildCollection.ChildNodeSwitched)
# def child_node_child_collection_switched_mutator(self, event):
#     assert isinstance(self, SuffixTreeNodeChildCollection), self
#     try:
#         del (self._child_node_ids[event.old_node_id])
#     except KeyError:
#         pass
#     self._child_node_ids[event.new_node_id] = event.new_edge_len
#     self._increment_version()
#     return self
#
#
# class SuffixTreeEdge(TimestampedVersionedEntity):
#     """An edge in the suffix tree.
#     """
#
#     class Created(Created):
#         pass
#
#     class AttributeChanged(AttributeChanged):
#         pass
#
#     class Shortened(TimestampedVersionedEntityEvent):
#         @property
#         def label(self):
#             return self.__dict__['label']
#
#         @property
#         def dest_node_id(self):
#             return self.__dict__['dest_node_id']
#
#     class Discarded(Discarded):
#         pass
#
#     def __init__(self, label, source_node_id, dest_node_id, **kwargs):
#         super(SuffixTreeEdge, self).__init__(**kwargs)
#         self._label = label
#         self._source_node_id = source_node_id
#         self._dest_node_id = dest_node_id
#
#     @attribute
#     def label(self):
#         """Index of start of string part represented by this edge.
#         """
#         return self._label
#
#     @attribute
#     def source_node_id(self):
#         """Id of source node of edge.
#         """
#         return self._source_node_id
#
#     @attribute
#     def dest_node_id(self):
#         """Id of destination node of edge.
#         """
#         return self._dest_node_id
#
#     @property
#     def length(self):
#         """Number of chars in the string part represented by this edge.
#         """
#         return len(self.label) - 1
#
#     def __repr__(self):
#         return ("Edge(id='{}' source='{}' dest='{}', label='{}')"
#                 "".format(self.id, self.source_node_id, self.dest_node_id, self.label[:30]))
#
#     def shorten(self, label, dest_node_id):
#         self._assert_not_discarded()
#         event = SuffixTreeEdge.Shortened(
#             originator_id=self._id,
#             originator_version=self.___version__,
#             label=label,
#             dest_node_id=dest_node_id,
#         )
#         self._apply(event)
#         publish(event)
#
#     @staticmethod
#     def _mutator(initial, event):
#         return suffix_tree_edge_mutator(initial, event)
#
#
# @mutator
# def suffix_tree_edge_mutator(initial, event):
#     return mutate_entity(initial, event)
#
#
# @suffix_tree_edge_mutator.register(SuffixTreeEdge.Shortened)
# def suffix_tree_edge_shortened_mutator(self, event):
#     assert isinstance(event, SuffixTreeEdge.Shortened), event
#     assert isinstance(self, SuffixTreeEdge), type(self)
#     self._validate_originator(event)
#     self._label = event.label
#     self._dest_node_id = event.dest_node_id
#     self._increment_version()
#     return self
#
#
# class Suffix(object):
#     """Represents a suffix from first_char_index to last_char_index.
#     """
#
#     def __init__(self, source_node_id, first_char_index, last_char_index):
#         """
#         :type source_node_id: str
#             Index of node where this suffix starts.
#
#         :type first_char_index: str
#             Index of start of suffix in string.
#
#         :type last_char_index: str
#             Index of end of suffix in string.
#         """
#         assert isinstance(source_node_id, str)
#         assert isinstance(first_char_index, int)
#         assert isinstance(last_char_index, int)
#         assert source_node_id is not None
#         self.source_node_id = source_node_id
#         self.first_char_index = first_char_index
#         self.last_char_index = last_char_index
#
#     @property
#     def length(self):
#         """Number of chars in string.
#         """
#         return self.last_char_index - self.first_char_index
#
#     def explicit(self):
#         """A suffix is explicit if it ends on a node. first_char_index
#         is set greater than last_char_index to indicate this.
#         """
#         return self.first_char_index > self.last_char_index
#
#     def implicit(self):
#         return self.last_char_index >= self.first_char_index
#
#     def __repr__(self):
#         return "Suffix(implicit={} first={}, last={}, node={})".format(self.implicit(), self.first_char_index,
#                                                                        self.last_char_index, self.source_node_id)
#
#
# # Factory methods.
#
# def register_new_node(suffix_node_id=None, string_id=None, is_leaf=False, is_root=False):
#     """Factory method, registers new node.
#     """
#     # Make a unique ID.
#     node_id = uuid4().hex
#
#     # Instantiate a Created event.
#     created_event = SuffixTreeNode.Created(
#         originator_id=node_id,
#         suffix_node_id=suffix_node_id,
#         string_id=string_id,
#         is_leaf=is_leaf,
#         is_root=is_root,
#     )
#
#     # Make the new Node entity.
#     new_node = SuffixTreeNode.mutate(event=created_event)
#
#     # Publish the Created event.
#     publish(created_event)
#
#     # Also create a new child collection, to
#     # avoid any contention around this event.
#     register_new_node_child_collection(node_id)
#
#     # Return the new node.
#     return new_node
#
#
# def register_new_node_child_collection(node_id):
#     """Factory method, registers new node child collection.
#     """
#     event = SuffixTreeNodeChildCollection.Created(
#         originator_id=node_id,
#     )
#     entity = SuffixTreeNodeChildCollection.mutate(event=event)
#     publish(event)
#     return entity
#
#
# def register_new_stringid_collection(node_id):
#     """Factory method, registers new collection of string IDs.
#     """
#     event = StringidCollection.Created(
#         originator_id=node_id,
#     )
#     entity = StringidCollection.mutate(event=event)
#     publish(event)
#     return entity
#
#
# def make_edge_id(source_node_id, first_char):
#     """Returns a string made from given params.
#     """
#     # assert STRING_ID_PADDING_RIGHT not in first_char
#     # assert STRING_ID_PADDING_RIGHT not in source_node_id
#     return "{}::{}".format(source_node_id, first_char)
#
#
# def register_new_edge(edge_id, label, source_node_id, dest_node_id):
#     """Factory method, registers new edge.
#     """
#     event = SuffixTreeEdge.Created(
#         originator_id=edge_id,
#         label=label,
#         source_node_id=source_node_id,
#         dest_node_id=dest_node_id,
#     )
#     entity = SuffixTreeEdge.mutate(event=event)
#     publish(event)
#     return entity
#
#
# def register_new_suffix_tree(case_insensitive=False):
#     """Factory method, returns new suffix tree object.
#     """
#     assert isinstance(case_insensitive, bool)
#
#     suffix_tree_id = uuid4().hex
#
#     root_node = register_new_node(is_root=True)
#     assert isinstance(root_node, SuffixTreeNode)
#
#     event = GeneralizedSuffixTree.Created(
#         originator_id=suffix_tree_id,
#         root_node_id=root_node.id,
#         case_insensitive=case_insensitive,
#     )
#     entity = GeneralizedSuffixTree.mutate(event=event)
#
#     assert isinstance(entity, GeneralizedSuffixTree)
#
#     # entity.nodes[root_node.id] = root_node
#
#     publish(event)
#
#     return entity
#
#
# # Repositories.
#
# class GeneralizedSuffixTreeRepository(AbstractEntityRepository):
#     pass
#
#
# class NodeRepository(AbstractEntityRepository):
#     pass
#
#
# class EdgeRepository(AbstractEntityRepository):
#     pass
