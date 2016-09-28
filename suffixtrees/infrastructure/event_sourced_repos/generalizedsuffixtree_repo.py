from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository
from suffixtrees.domain.model.generalizedsuffixtree import GeneralizedSuffixTree, GeneralizedSuffixTreeRepository, NodeRepository, SuffixTreeNode, SuffixTreeEdge, \
    EdgeRepository


class GeneralizedSuffixTreeRepo(EventSourcedRepository, GeneralizedSuffixTreeRepository):
    domain_class = GeneralizedSuffixTree


class NodeRepo(EventSourcedRepository, NodeRepository):
    domain_class = SuffixTreeNode


class EdgeRepo(EventSourcedRepository, EdgeRepository):
    domain_class = SuffixTreeEdge
