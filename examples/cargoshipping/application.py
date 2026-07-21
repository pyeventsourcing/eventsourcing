from __future__ import annotations

from typing import TYPE_CHECKING

from eventsourcing.pydantic import AggregatesApplication
from examples.cargoshipping.domainmodel import (
    REGISTERED_ROUTES,
    Cargo,
    HandlingActivity,
    Itinerary,
    Location,
)

if TYPE_CHECKING:
    from datetime import datetime


class BookingApplication(AggregatesApplication):
    def book_new_cargo(
        self,
        origin: Location,
        destination: Location,
        arrival_deadline: datetime,
    ) -> str:
        cargo = Cargo.new_booking(origin, destination, arrival_deadline)
        self.save(cargo)
        return cargo.id

    def change_destination(self, tracking_id: str, destination: Location) -> None:
        cargo = self.get_cargo(tracking_id)
        cargo.change_destination(destination)
        self.save(cargo)

    def request_possible_routes_for_cargo(self, tracking_id: str) -> list[Itinerary]:
        cargo = self.get_cargo(tracking_id)
        from_location = (cargo.last_known_location or cargo.origin).value
        to_location = cargo.destination.value
        try:
            possible_routes = REGISTERED_ROUTES[(from_location, to_location)]
        except KeyError:
            msg = f"Can't find routes from {from_location} to {to_location}"
            raise ValueError(msg) from None

        return possible_routes

    def assign_route(self, tracking_id: str, itinerary: Itinerary) -> None:
        cargo = self.get_cargo(tracking_id)
        cargo.assign_route(itinerary)
        self.save(cargo)

    def register_handling_event(
        self,
        tracking_id: str,
        voyage_number: str | None,
        location: Location,
        handing_activity: HandlingActivity,
    ) -> None:
        cargo = self.get_cargo(tracking_id)
        cargo.register_handling_event(
            tracking_id,
            voyage_number,
            location,
            handing_activity,
        )
        self.save(cargo)

    def get_cargo(self, tracking_id: str) -> Cargo:
        return self.repository.get(tracking_id, Cargo)
