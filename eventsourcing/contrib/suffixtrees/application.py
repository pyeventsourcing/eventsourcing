import datetime

from eventsourcing.example.application import ApplicationWithPersistencePolicies
from eventsourcing.contrib.suffixtrees.domain.model.generalizedsuffixtree import GeneralizedSuffixTree, \
    register_new_suffix_tree
from eventsourcing.contrib.suffixtrees.domain.services.generalizedsuffixtree import find_substring_edge, \
    get_string_ids, has_substring
from eventsourcing.contrib.suffixtrees.infrastructure.respositories.generalizedsuffixtree_repo import EdgeRepo, \
    GeneralizedSuffixTreeRepo, NodeChildCollectionRepo, NodeRepo, StringidCollectionRepo


class SuffixTreeApplication(ApplicationWithPersistencePolicies):
    def __init__(self, **kwargs):
        super(SuffixTreeApplication, self).__init__(**kwargs)
        self.suffix_tree_repo = GeneralizedSuffixTreeRepo(self.event_store)
        self.node_repo = NodeRepo(self.event_store)
        self.node_child_collection_repo = NodeChildCollectionRepo(self.event_store)
        self.edge_repo = EdgeRepo(self.event_store)
        self.stringid_collection_repo = StringidCollectionRepo(self.event_store)

    def close(self):
        super(SuffixTreeApplication, self).close()
        self.suffix_tree_repo = None
        self.node_repo = None
        self.node_child_collection_repo = None
        self.edge_repo = None
        self.stringid_collection_repo = None

    def register_new_suffix_tree(self, case_insensitive=False):
        """Returns a new suffix tree entity.
        """
        suffix_tree = register_new_suffix_tree(case_insensitive=case_insensitive)
        suffix_tree._node_repo = self.node_repo
        suffix_tree._node_child_collection_repo = self.node_child_collection_repo
        suffix_tree._edge_repo = self.edge_repo
        suffix_tree._stringid_collection_repo = self.stringid_collection_repo
        return suffix_tree

    def get_suffix_tree(self, suffix_tree_id):
        """Returns a suffix tree entity, equipped with node and edge repos it (at least at the moment) needs.
        """
        suffix_tree = self.suffix_tree_repo[suffix_tree_id]
        assert isinstance(suffix_tree, GeneralizedSuffixTree)
        suffix_tree._node_repo = self.node_repo
        suffix_tree._node_child_collection_repo = self.node_child_collection_repo
        suffix_tree._edge_repo = self.edge_repo
        suffix_tree._stringid_collection_repo = self.stringid_collection_repo
        return suffix_tree

    def find_string_ids(self, substring, suffix_tree_id, limit=None):
        """Returns a set of IDs for strings that contain the given substring.
        """

        # Find an edge for the substring.
        edge, ln = self.find_substring_edge(substring=substring, suffix_tree_id=suffix_tree_id)

        # If there isn't an edge, return an empty set.
        if edge is None:
            return set()

        # Get all the string IDs beneath the edge's destination node.
        string_ids = get_string_ids(
            node_id=edge.dest_node_id,
            node_repo=self.node_repo,
            node_child_collection_repo=self.node_child_collection_repo,
            stringid_collection_repo=self.stringid_collection_repo,
            length_until_end=edge.length + 1 - ln,
            limit=limit
        )

        # Return a set of string IDs.
        return set(string_ids)

    def find_substring_edge(self, substring, suffix_tree_id):
        """Returns an edge that matches the given substring.
        """
        suffix_tree = self.suffix_tree_repo[suffix_tree_id]
        started = datetime.datetime.now()
        edge, ln = find_substring_edge(substring=substring, suffix_tree=suffix_tree, edge_repo=self.edge_repo)
        # if edge is not None:
        #     print("Got edge for substring '{}': {}".format(substring, edge))
        # else:
        #     print("No edge for substring '{}'".format(substring))
        print(" - searched for edge in {} for substring: '{}'".format(datetime.datetime.now() - started, substring))
        return edge, ln

    def has_substring(self, substring, suffix_tree_id):
        suffix_tree = self.suffix_tree_repo[suffix_tree_id]
        return has_substring(
            substring=substring,
            suffix_tree=suffix_tree,
            edge_repo=self.edge_repo,
        )
