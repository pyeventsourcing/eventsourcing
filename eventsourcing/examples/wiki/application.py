from typing import Dict, cast
from uuid import UUID

from eventsourcing.application import AggregateNotFound, Application
from eventsourcing.domain import Aggregate
from eventsourcing.examples.wiki.domainmodel import Index, Page


class PageNotFound(Exception):
    pass


class WikiApplication(Application[Aggregate]):
    env = {"COMPRESSOR_TOPIC": "gzip"}
    snapshotting_intervals = {Page: 10}

    def create_page(self, title: str, slug: str) -> None:
        page = Page(title=title)
        index_entry = Index(slug, ref=page.id)
        self.save(page, index_entry)

    def get_page(self, slug: str) -> Dict[str, str]:
        page = self._get_page(slug)
        return {"title": page.title, "body": page.body}

    def update_title(self, slug: str, title: str) -> None:
        page = self._get_page(slug)
        page.update_title(title=title)
        self.save(page)

    def update_slug(self, old_slug: str, new_slug: str) -> None:
        old_index = self._get_index(old_slug)
        try:
            new_index = self._get_index(new_slug)
        except AggregateNotFound:
            new_index = Index(new_slug, old_index.ref)
        old_index.update_ref(None)
        self.save(old_index, new_index)

    def update_body(self, slug: str, body: str) -> None:
        page = self._get_page(slug)
        page.update_body(body)
        self.save(page)

    def _get_page(self, slug: str) -> Page:
        try:
            index = self._get_index(slug)
        except AggregateNotFound:
            raise PageNotFound(slug)
        if index.ref is None:
            raise PageNotFound(slug)
        return cast(Page, self.repository.get(index.ref))

    def _get_index(self, slug: str) -> Index:
        return cast(Index, self.repository.get(Index.create_id(slug)))
