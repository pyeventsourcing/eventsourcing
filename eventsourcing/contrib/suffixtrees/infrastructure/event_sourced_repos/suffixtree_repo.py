from eventsourcing.contrib.suffixtrees.domain.model.suffixtree import SuffixTree, SuffixTreeRepository, NodeRepository, Node, Edge, \
    EdgeRepository
from eventsourcing.infrastructure.event_sourced_repo import EventSourcedRepository


class SuffixTreeRepo(EventSourcedRepository, SuffixTreeRepository):
    domain_class = SuffixTree


class NodeRepo(EventSourcedRepository, NodeRepository):
    domain_class = Node


class EdgeRepo(EventSourcedRepository, EdgeRepository):
    domain_class = Edge
