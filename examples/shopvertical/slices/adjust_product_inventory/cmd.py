from __future__ import annotations

from typing import TYPE_CHECKING, override

from eventsourcing.domain import StreamEvent
from examples.shopvertical.common import Command, get_events, put_events
from examples.shopvertical.events import AdjustedProductInventory
from examples.shopvertical.exceptions import ProductNotFoundInShopError

if TYPE_CHECKING:
    from examples.shopvertical.common import Events


class AdjustProductInventory(Command):
    product_id: str
    adjustment: int

    @override
    def handle(self, events: Events) -> Events:
        if not events:
            raise ProductNotFoundInShopError
        return (
            StreamEvent(
                decision=AdjustedProductInventory(
                    adjustment=self.adjustment,
                ),
                stream_id=self.product_id,
                stream_position=len(events) + 1,
            ),
        )

    @override
    def execute(self) -> int | None:
        return put_events(self.handle(get_events(self.product_id)))
