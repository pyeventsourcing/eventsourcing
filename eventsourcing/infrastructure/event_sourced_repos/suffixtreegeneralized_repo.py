from eventsourcing.domain.model.suffixtreegeneralized import SuffixTreeGeneralized, SuffixTreeGeneralizedRepository, NodeRepository, SuffixTreeNode, SuffixTreeEdge, \
    EdgeRepository
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository


class SuffixTreeGeneralizedRepo(EventSourcedRepository, SuffixTreeGeneralizedRepository):
    domain_class = SuffixTreeGeneralized


class NodeRepo(EventSourcedRepository, NodeRepository):
    domain_class = SuffixTreeNode


class EdgeRepo(EventSourcedRepository, EdgeRepository):
    domain_class = SuffixTreeEdge
