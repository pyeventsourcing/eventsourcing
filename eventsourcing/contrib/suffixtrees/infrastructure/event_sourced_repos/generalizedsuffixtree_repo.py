from eventsourcing.contrib.suffixtrees.domain.model.generalizedsuffixtree import GeneralizedSuffixTree, \
    GeneralizedSuffixTreeRepository, NodeRepository, SuffixTreeNode, SuffixTreeEdge, EdgeRepository, \
    SuffixTreeNodeChildCollection
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository


class GeneralizedSuffixTreeRepo(EventSourcedRepository, GeneralizedSuffixTreeRepository):
    domain_class = GeneralizedSuffixTree


class NodeRepo(EventSourcedRepository, NodeRepository):
    domain_class = SuffixTreeNode


class NodeChildCollectionRepo(EventSourcedRepository, NodeRepository):
    domain_class = SuffixTreeNodeChildCollection


class EdgeRepo(EventSourcedRepository, EdgeRepository):
    domain_class = SuffixTreeEdge
