from eventsourcing.contrib.suffixtrees.domain.model.generalizedsuffixtree import GeneralizedSuffixTree, \
    GeneralizedSuffixTreeRepository, NodeRepository, SuffixTreeNode, SuffixTreeEdge, EdgeRepository, \
    SuffixTreeNodeChildCollection, StringidCollection
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository
from eventsourcing.infrastructure.event_sourced_repos.collection_repo import CollectionRepo


class GeneralizedSuffixTreeRepo(EventSourcedRepository, GeneralizedSuffixTreeRepository):
    domain_class = GeneralizedSuffixTree


class NodeRepo(EventSourcedRepository, NodeRepository):
    domain_class = SuffixTreeNode


class NodeChildCollectionRepo(EventSourcedRepository, NodeRepository):
    domain_class = SuffixTreeNodeChildCollection


class EdgeRepo(EventSourcedRepository, EdgeRepository):
    domain_class = SuffixTreeEdge


class StringidCollectionRepo(CollectionRepo):
    domain_class = StringidCollection
