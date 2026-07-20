from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.domain import AggregateEvent
from examples.shopvertical.common import Command, get_events, put_events
from examples.shopvertical.events import ClearedCart, SubmittedCart
from examples.shopvertical.exceptions import CartAlreadySubmittedError

if TYPE_CHECKING:
    from examples.shopvertical.common import Events


class ClearCart(Command):
    cart_id: str

    def handle(self, events: Events) -> Events:
        is_submitted = False
        for event in events:
            match event.decision:
                case SubmittedCart():
                    is_submitted = True

        if is_submitted:
            raise CartAlreadySubmittedError

        return (
            AggregateEvent(
                decision=ClearedCart(),
                originator_id=self.cart_id,
                originator_version=len(events) + 1,
            ),
        )

    def execute(self) -> int | None:
        return put_events(self.handle(get_events(self.cart_id)))
