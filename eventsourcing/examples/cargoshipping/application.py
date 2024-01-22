from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, cast

from eventsourcing.application import Application
from eventsourcing.examples.cargoshipping.domainmodel import (
    REGISTERED_ROUTES,
    Cargo,
    HandlingActivity,
    Itinerary,
    Leg,
    Location,
)
from eventsourcing.persistence import Transcoder, Transcoding

if TYPE_CHECKING:  # pragma: nocover
    from datetime import datetime
    from uuid import UUID


class LocationAsName(Transcoding):
    type = Location
    name = "location"

    def encode(self, obj: Location) -> str:
        return obj.name

    def decode(self, data: str) -> Location:
        assert isinstance(data, str)
        return Location[data]


class HandlingActivityAsName(Transcoding):
    type = HandlingActivity
    name = "handling_activity"

    def encode(self, obj: HandlingActivity) -> str:
        return obj.name

    def decode(self, data: str) -> HandlingActivity:
        assert isinstance(data, str)
        return HandlingActivity[data]


class ItineraryAsDict(Transcoding):
    type = Itinerary
    name = "itinerary"

    def encode(self, obj: Itinerary) -> Dict[str, Any]:
        return obj.__dict__

    def decode(self, data: Dict[str, Any]) -> Itinerary:
        assert isinstance(data, dict)
        return Itinerary(**data)


class LegAsDict(Transcoding):
    type = Leg
    name = "leg"

    def encode(self, obj: Leg) -> Dict[str, Any]:
        return obj.__dict__

    def decode(self, data: Dict[str, Any]) -> Leg:
        assert isinstance(data, dict)
        return Leg(**data)


class BookingApplication(Application):
    def register_transcodings(self, transcoder: Transcoder) -> None:
        super().register_transcodings(transcoder)
        transcoder.register(LocationAsName())
        transcoder.register(HandlingActivityAsName())
        transcoder.register(ItineraryAsDict())
        transcoder.register(LegAsDict())

    def book_new_cargo(
        self,
        origin: Location,
        destination: Location,
        arrival_deadline: datetime,
    ) -> UUID:
        cargo = Cargo.new_booking(origin, destination, arrival_deadline)
        self.save(cargo)
        return cargo.id

    def change_destination(self, tracking_id: UUID, destination: Location) -> None:
        cargo = self.get_cargo(tracking_id)
        cargo.change_destination(destination)
        self.save(cargo)

    def request_possible_routes_for_cargo(self, tracking_id: UUID) -> List[Itinerary]:
        cargo = self.get_cargo(tracking_id)
        from_location = (cargo.last_known_location or cargo.origin).value
        to_location = cargo.destination.value
        try:
            possible_routes = REGISTERED_ROUTES[(from_location, to_location)]
        except KeyError:
            msg = f"Can't find routes from {from_location} to {to_location}"
            raise ValueError(msg) from None

        return possible_routes

    def assign_route(self, tracking_id: UUID, itinerary: Itinerary) -> None:
        cargo = self.get_cargo(tracking_id)
        cargo.assign_route(itinerary)
        self.save(cargo)

    def register_handling_event(
        self,
        tracking_id: UUID,
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

    def get_cargo(self, tracking_id: UUID) -> Cargo:
        return cast(Cargo, self.repository.get(tracking_id))
