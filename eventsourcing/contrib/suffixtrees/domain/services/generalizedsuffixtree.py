# from eventsourcing.exceptions import RepositoryKeyError
#
#
# def get_string_ids(node_id, node_repo, node_child_collection_repo, stringid_collection_repo, length_until_end=0,
#                    edge_length=0,
#                    limit=None, hop_count=0, hop_max=None):
#     """Generator that yields unique string IDs from leaf nodes as they are discovered,
#     by performing a depth first search on the suffix tree from the given node.
#     """
#     stack = list()
#
#     # _print("Searching for string IDs from node: {}".format(node_id))
#
#     stack.append((node_id, edge_length, None))
#     unique_node_ids = set(node_id)
#     unique_string_ids = set()
#     cum_lengths_until_end = {None: length_until_end}
#     while stack:
#
#         (node_id, edge_length, parent_node_id) = stack.pop()
#
#         length_until_end = cum_lengths_until_end[parent_node_id] + edge_length
#         cum_lengths_until_end[node_id] = length_until_end
#
#         node = node_repo[node_id]
#         assert isinstance(node, SuffixTreeNode)
#
#         try:
#             stringid_collection = stringid_collection_repo[node_id]
#         except KeyError:
#             stringid_collection = None
#         else:
#             assert isinstance(stringid_collection, StringidCollection)
#
#         if stringid_collection and stringid_collection.items:
#
#             # Deduplicate string IDs (the substring might match more than one suffix in any given string).
#             for string_id in stringid_collection.items:
#                 if string_id in unique_string_ids:
#                     continue
#
#                 # Check the match doesn't encroach upon the string's extension.
#                 extension_length = len(STRING_ID_END)
#                 if length_until_end < extension_length:
#                     continue
#
#                 # print("Found string ID '{}' at node: {}".format(string_id, node_id))
#
#                 # Remember the string ID, we only want one node per string ID.
#                 unique_string_ids.add(string_id)
#
#                 # Yield the string ID.
#                 yield string_id
#
#                 # Check the limit, stop if we've had enough string IDs.
#                 if limit is not None and len(unique_string_ids) >= limit:
#                     return
#
#         # Check the hop count before getting the child collection.
#         if hop_max is None or hop_count < hop_max:
#             try:
#                 node_child_collection = node_child_collection_repo[node_id]
#             except RepositoryKeyError:
#                 # It doesn't matter if there isn't a child collection.
#                 pass
#             else:
#                 # Since there's a collection, put the child nodes on the stack.
#                 child_node_ids = node_child_collection._child_node_ids.copy()
#                 for (child_node_id, edge_length) in child_node_ids.items():
#                     # Check the hop count, stop if we've seen enough tree nodes.
#                     #  - this works by choking off the stack, but we continue
#                     #    to process everything on the stack after this condition
#                     #    which saves putting loads of things on the stack that
#                     #    won't be used, and walking more tree than is necessary
#                     if hop_max is not None and hop_count >= hop_max:
#                         break
#
#                     # Put the child node on the stack.
#                     # if child_node_id not in unique_node_ids:
#                     if child_node_id != node_id:
#                         unique_node_ids.add(child_node_id)
#                         stack.append((child_node_id, edge_length, node.id))
#
#                     # Increase the hop count.
#                     hop_count += 1
#
#
# def find_substring_edge(substring, suffix_tree, edge_repo):
#     """Returns the last edge, if substring in tree, otherwise None.
#     """
#     assert isinstance(substring, str)
#     assert isinstance(suffix_tree, GeneralizedSuffixTree)
#     assert isinstance(edge_repo, EdgeRepository)
#     if not substring:
#         return None, None
#     if suffix_tree.case_insensitive:
#         substring = substring.lower()
#     curr_node_id = suffix_tree.root_node_id
#     i = 0
#     while i < len(substring):
#         edge_id = make_edge_id(curr_node_id, substring[i])
#         try:
#             edge = edge_repo[edge_id]
#         except RepositoryKeyError:
#             return None, None
#         ln = min(edge.length + 1, len(substring) - i)
#         if substring[i:i + ln] != edge.label[:ln]:
#             return None, None
#         i += edge.length + 1
#         curr_node_id = edge.dest_node_id
#     return edge, ln
#
#
# def has_substring(substring, suffix_tree, edge_repo):
#     edge, ln = find_substring_edge(substring, suffix_tree, edge_repo)
#     return edge is not None
