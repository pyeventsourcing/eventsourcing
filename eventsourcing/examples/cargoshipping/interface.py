from datetime import datetime
from typing import Any, List, Optional, Tuple, Union
from uuid import UUID

from eventsourcing.examples.cargoshipping.application import BookingApplication
from eventsourcing.examples.cargoshipping.domainmodel import (
    CargoDetails,
    HandlingActivity,
    Itinerary,
    ItineraryDetails,
    LegDetails,
    Location,
)


class BookingService(object):
    """
    Presents an application interface that uses
    simple types of object (str, bool, datetime).
    """

    def __init__(self, app: BookingApplication):
        self.app = app

    def book_new_cargo(
        self,
        origin: str,
        destination: str,
        arrival_deadline: datetime,
    ) -> str:
        tracking_id = self.app.book_new_cargo(
            Location[origin],
            Location[destination],
            arrival_deadline,
        )
        return str(tracking_id)

    def get_cargo_details(self, tracking_id: str) -> CargoDetails:
        cargo = self.app.get_cargo(UUID(tracking_id))

        # Present 'next_expected_activity'.
        next_expected_activity: Optional[Union[Tuple[Any, Any], Tuple[Any, Any, Any]]]
        if cargo.next_expected_activity is None:
            next_expected_activity = None
        elif len(cargo.next_expected_activity) == 2:
            next_expected_activity = (
                cargo.next_expected_activity[0].value,
                cargo.next_expected_activity[1].value,
            )
        elif len(cargo.next_expected_activity) == 3:
            next_expected_activity = (
                cargo.next_expected_activity[0].value,
                cargo.next_expected_activity[1].value,
                cargo.next_expected_activity[2],
            )
        else:
            raise Exception(
                "Invalid next expected activity: {}".format(
                    cargo.next_expected_activity
                )
            )

        # Present 'last_known_location'.
        if cargo.last_known_location is None:
            last_known_location = None
        else:
            last_known_location = cargo.last_known_location.value

        # Present the cargo details.
        return {
            "id": str(cargo.id),
            "origin": cargo.origin.value,
            "destination": cargo.destination.value,
            "arrival_deadline": cargo.arrival_deadline,
            "transport_status": cargo.transport_status,
            "routing_status": cargo.routing_status,
            "is_misdirected": cargo.is_misdirected,
            "estimated_time_of_arrival": cargo.estimated_time_of_arrival,
            "next_expected_activity": next_expected_activity,
            "last_known_location": last_known_location,
            "current_voyage_number": cargo.current_voyage_number,
        }

    def change_destination(self, tracking_id: str, destination: str) -> None:
        self.app.change_destination(UUID(tracking_id), Location[destination])

    def request_possible_routes_for_cargo(self, tracking_id: str) -> List[dict]:
        routes = self.app.request_possible_routes_for_cargo(UUID(tracking_id))
        return [self.dict_from_itinerary(route) for route in routes]

    def dict_from_itinerary(self, itinerary: Itinerary) -> ItineraryDetails:
        legs_details = []
        for leg in itinerary.legs:
            leg_details: LegDetails = {
                "origin": leg.origin,
                "destination": leg.destination,
                "voyage_number": leg.voyage_number,
            }
            legs_details.append(leg_details)
        route_details: ItineraryDetails = {
            "origin": itinerary.origin,
            "destination": itinerary.destination,
            "legs": legs_details,
        }
        return route_details

    def assign_route(
        self,
        tracking_id: str,
        route_details: ItineraryDetails,
    ) -> None:
        routes = self.app.request_possible_routes_for_cargo(UUID(tracking_id))
        for route in routes:
            if route_details == self.dict_from_itinerary(route):
                self.app.assign_route(UUID(tracking_id), route)

    def register_handling_event(
        self,
        tracking_id: str,
        voyage_number: Optional[str],
        location: str,
        handling_activity: str,
    ) -> None:
        self.app.register_handling_event(
            UUID(tracking_id),
            voyage_number,
            Location[location],
            HandlingActivity[handling_activity],
        )


# Stub function that picks an itinerary from a list of possible itineraries.
def select_preferred_itinerary(
    itineraries: List[ItineraryDetails],
) -> ItineraryDetails:
    return itineraries[0]
