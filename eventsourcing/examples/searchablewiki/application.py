from typing import Any, Dict, List, Optional, Union, cast

from eventsourcing.domain import DomainEventProtocol, MutableOrImmutableAggregate
from eventsourcing.examples.searchablewiki.persistence import (
    SearchableWikiApplicationRecorder,
    SearchableWikiInfrastructureFactory,
)
from eventsourcing.examples.wiki.application import PageDetailsType, WikiApplication
from eventsourcing.examples.wiki.domainmodel import Page
from eventsourcing.persistence import InfrastructureFactory, Recording
from eventsourcing.utils import Environment


class SearchableWikiApplication(WikiApplication):
    def construct_factory(self, env: Environment) -> InfrastructureFactory:
        return SearchableWikiInfrastructureFactory(env)

    def save(
        self,
        *objs: Optional[Union[MutableOrImmutableAggregate, DomainEventProtocol]],
        **kwargs: Any,
    ) -> List[Recording]:
        insert_page_bodies: Dict[str, str] = {}
        update_page_bodies: Dict[str, str] = {}
        for obj in objs:
            if isinstance(obj, Page):
                if obj.version == len(obj.pending_events):
                    insert_page_bodies[obj.slug] = obj.body
                else:
                    update_page_bodies[obj.slug] = obj.body
        kwargs["insert_page_bodies"] = insert_page_bodies
        kwargs["update_page_bodies"] = update_page_bodies
        return super().save(*objs, **kwargs)

    def search(self, query: str) -> List[PageDetailsType]:
        pages = []
        recorder = cast(SearchableWikiApplicationRecorder, self.recorder)
        for slug in recorder.search_page_bodies(query):
            page = self.get_page_details(slug)
            pages.append(page)
        return pages
