from datetime import datetime
from typing import List, Optional
from uuid import UUID

from eventsourcing.application import Application
from eventsourcing.eventmapper import Transcoder, Transcoding
from eventsourcing.examples.cargoshipping.domainmodel import (
    Cargo,
    HandlingActivity,
    Itinerary,
    Leg,
    Location,
    REGISTERED_ROUTES,
)

# Cargo aggregates exist within an application, which
# provides "application service" methods for clients.


class LocationAsName(Transcoding):
    type = Location
    name = "location"

    def encode(self, o: Location) -> str:
        return o.name

    def decode(self, d: str) -> Location:
        assert isinstance(d, str)
        return Location[d]


class HandlingActivityAsName(Transcoding):
    type = HandlingActivity
    name = "handling_activity"

    def encode(self, o: HandlingActivity) -> str:
        return o.name

    def decode(self, d: str) -> HandlingActivity:
        assert isinstance(d, str)
        return HandlingActivity[d]


class ItineraryAsDict(Transcoding):
    type = Itinerary
    name = "itinerary"

    def encode(self, o: Itinerary) -> dict:
        return o.__dict__

    def decode(self, d: dict) -> Itinerary:
        assert isinstance(d, dict)
        return Itinerary(**d)


class LegAsDict(Transcoding):
    type = Leg
    name = "leg"

    def encode(self, o: Leg) -> dict:
        return o.__dict__

    def decode(self, d: dict) -> Leg:
        assert isinstance(d, dict)
        return Leg(**d)


class BookingApplication(Application):
    def register_transcodings(
        self, transcoder: Transcoder
    ):
        super(
            BookingApplication, self
        ).register_transcodings(transcoder)
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
        cargo = Cargo.new_booking(
            origin, destination, arrival_deadline
        )
        self.save(cargo)
        return cargo.uuid

    def change_destination(
        self, tracking_id: UUID, destination: Location
    ) -> None:
        cargo = self.get_cargo(tracking_id)
        cargo.change_destination(destination)
        self.save(cargo)

    def request_possible_routes_for_cargo(
        self, tracking_id: UUID
    ) -> List[Itinerary]:
        cargo = self.get_cargo(tracking_id)
        from_location = (
            cargo.last_known_location or cargo.origin
        ).value
        to_location = cargo.destination.value
        try:
            possible_routes = REGISTERED_ROUTES[
                (from_location, to_location)
            ]
        except KeyError:
            raise Exception(
                "Can't find routes from {} to {}".format(
                    from_location, to_location
                )
            )

        return possible_routes

    def assign_route(
        self, tracking_id: UUID, itinerary: Itinerary
    ) -> None:
        cargo = self.get_cargo(tracking_id)
        cargo.assign_route(itinerary)
        self.save(cargo)

    def register_handling_event(
        self,
        tracking_id: UUID,
        voyage_number: Optional[str],
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
        cargo = self.repository.get(tracking_id)
        assert isinstance(cargo, Cargo)
        return cargo
