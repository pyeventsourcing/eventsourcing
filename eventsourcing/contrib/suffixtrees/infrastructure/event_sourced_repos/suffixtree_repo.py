from eventsourcing.contrib.suffixtrees.domain.model.suffixtree import Edge, EdgeRepository, Node, NodeRepository, \
    SuffixTree, SuffixTreeRepository
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


class SuffixTreeRepo(EventSourcedRepository, SuffixTreeRepository):
    domain_class = SuffixTree


class NodeRepo(EventSourcedRepository, NodeRepository):
    domain_class = Node


class EdgeRepo(EventSourcedRepository, EdgeRepository):
    domain_class = Edge
