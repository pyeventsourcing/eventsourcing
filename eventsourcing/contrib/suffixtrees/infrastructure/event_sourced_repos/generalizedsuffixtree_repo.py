from eventsourcing.contrib.suffixtrees.domain.model.generalizedsuffixtree import EdgeRepository, \
    GeneralizedSuffixTree, GeneralizedSuffixTreeRepository, NodeRepository, StringidCollection, \
    SuffixTreeEdge, SuffixTreeNode, SuffixTreeNodeChildCollection
from eventsourcing.infrastructure.repositories.collection_repo import CollectionRepository
from eventsourcing.infrastructure.eventsourcedrepository import EventSourcedRepository


class GeneralizedSuffixTreeRepo(EventSourcedRepository, GeneralizedSuffixTreeRepository):
    domain_class = GeneralizedSuffixTree


class NodeRepo(EventSourcedRepository, NodeRepository):
    domain_class = SuffixTreeNode


class NodeChildCollectionRepo(EventSourcedRepository, NodeRepository):
    domain_class = SuffixTreeNodeChildCollection


class EdgeRepo(EventSourcedRepository, EdgeRepository):
    domain_class = SuffixTreeEdge


class StringidCollectionRepo(CollectionRepository):
    domain_class = StringidCollection
