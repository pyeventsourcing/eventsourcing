import six

from eventsourcing.contrib.suffixtrees.domain.model.generalizedsuffixtree import SuffixTreeNode, STRING_ID_END, \
    GeneralizedSuffixTree, EdgeRepository, make_edge_id


def get_string_ids(node_id, node_repo, node_child_collection_repo, length_until_end=0, edge_length=0,
                   limit=None, hop_count=0, hop_max=None):
    """Generator that yields unique string IDs from leaf nodes as they are discovered,
    by performing a depth first search on the suffix tree from the given node.
    """
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

        # If it doesn't have a string ID, check for any children.
        string_id = node.string_id
        if string_id is None:

            # Check the hop count before getting the child collection.
            if hop_max is None or hop_count < hop_max:
                try:
                    node_child_collection = node_child_collection_repo[node_id]
                except KeyError:
                    # It doesn't matter if there isn't a child collection.
                    pass
                else:
                    # Since there's a collection, put the child nodes on the stack.
                    child_node_ids = node_child_collection._child_node_ids.copy()
                    for (child_node_id, edge_length) in child_node_ids.items():

                        # Check the hop count, stop if we've seen enough tree nodes.
                        if hop_max is not None and hop_count >= hop_max:
                            break

                        # Put the child node on the stack.
                        stack.append((child_node_id, edge_length, node.id))

                        # Increase the hop count.
                        hop_count += 1

        else:
            # Deduplicate string IDs (the substring might match more than one suffix in any given string).
            if string_id in unique_string_ids:
                continue

            # Check the match doesn't encroach upon the string's extension.
            extension_length = len(string_id) + len(STRING_ID_END)
            if length_until_end < extension_length:
                continue

            # Remember the string ID, we only want one node per string ID.
            unique_string_ids.add(string_id)

            # Yield the string ID.
            yield string_id

            # Check the limit, stop if we've had enough string IDs.
            if limit is not None and len(unique_string_ids) >= limit:
                raise StopIteration



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
