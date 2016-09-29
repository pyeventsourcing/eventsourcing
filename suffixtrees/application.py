import datetime

from eventsourcing.application.example.with_pythonobjects import ExampleApplicationWithPythonObjects
from suffixtrees.domain.model.generalizedsuffixtree import register_new_suffix_tree, find_substring_edge, has_substring
from suffixtrees.domain.services.generalizedsuffixtree import get_leaf_nodes
from suffixtrees.infrastructure.event_sourced_repos.generalizedsuffixtree_repo import GeneralizedSuffixTreeRepo, \
    NodeRepo, EdgeRepo


class SuffixTreeApplication(ExampleApplicationWithPythonObjects):

    def __init__(self, **kwargs):
        super(SuffixTreeApplication, self).__init__(**kwargs)
        self.suffix_tree_repo = GeneralizedSuffixTreeRepo(self.event_store)
        self.node_repo = NodeRepo(self.event_store)
        self.edge_repo = EdgeRepo(self.event_store)

    def register_new_suffixtree(self, string, case_insensitive=False):
        return register_new_suffix_tree(string, case_insensitive)

    def get_suffix_tree(self, suffix_tree_id):
        suffix_tree = self.suffix_tree_repo[suffix_tree_id]
        suffix_tree._node_repo = self.node_repo
        suffix_tree._edge_repo = self.edge_repo
        return suffix_tree

    def find_string_ids(self, substring, suffix_tree_id, limit=None):
        edge, ln = self.find_substring_edge(substring=substring, suffix_tree_id=suffix_tree_id)
        if edge is None:
            return set()

        leaf_nodes = get_leaf_nodes(
            node_id=edge.dest_node_id,
            node_repo=self.node_repo,
            length_until_end=edge.length + 1 - ln,
            limit=limit
        )

        return set((l.string_id for l in leaf_nodes))

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
