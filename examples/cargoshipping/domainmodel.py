from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from eventsourcing.decorator import triggers
from eventsourcing.pydantic import Aggregate, Decision
from eventsourcing.timestamp import datetime_now_with_tzinfo


class Location(Enum):
    """Locations in the world."""

    HAMBURG = "HAMBURG"
    HONGKONG = "HONGKONG"
    NEWYORK = "NEWYORK"
    STOCKHOLM = "STOCKHOLM"
    TOKYO = "TOKYO"

    NLRTM = "NLRTM"
    USDAL = "USDAL"
    AUMEL = "AUMEL"


class Leg(BaseModel):
    """Leg of an itinerary."""

    origin: str
    destination: str
    voyage_number: str


class Itinerary(BaseModel):
    """An itinerary along which cargo is shipped."""

    origin: str
    destination: str
    legs: tuple[Leg, ...]


class HandlingActivity(Enum):
    RECEIVE = "RECEIVE"
    LOAD = "LOAD"
    UNLOAD = "UNLOAD"
    CLAIM = "CLAIM"


# Custom static types.
LegDetails = dict[str, str]

ItineraryDetails = dict[str, str | list[LegDetails] | None]

NextExpectedActivity = tuple[HandlingActivity, Location, str] | None


# Some routes from one location to another.
REGISTERED_ROUTES = {
    ("HONGKONG", "STOCKHOLM"): [
        Itinerary(
            origin="HONGKONG",
            destination="STOCKHOLM",
            legs=(
                Leg(
                    origin="HONGKONG",
                    destination="NEWYORK",
                    voyage_number="V1",
                ),
                Leg(
                    origin="NEWYORK",
                    destination="STOCKHOLM",
                    voyage_number="V2",
                ),
            ),
        )
    ],
    ("TOKYO", "STOCKHOLM"): [
        Itinerary(
            origin="TOKYO",
            destination="STOCKHOLM",
            legs=(
                Leg(
                    origin="TOKYO",
                    destination="HAMBURG",
                    voyage_number="V3",
                ),
                Leg(
                    origin="HAMBURG",
                    destination="STOCKHOLM",
                    voyage_number="V4",
                ),
            ),
        )
    ],
}


class CargoEvent(Decision):
    timestamp: datetime = Field(default_factory=datetime_now_with_tzinfo)


class BookingStarted(CargoEvent):
    origin: Location
    destination: Location
    arrival_deadline: datetime


class DestinationChanged(CargoEvent):
    destination: Location


class RouteAssigned(CargoEvent):
    route: Itinerary


class HandlingEventRegistered(CargoEvent):
    tracking_id: str
    voyage_number: str | None
    location: Location
    handling_activity: HandlingActivity


class Cargo(Aggregate):
    """The Cargo aggregate is an event-sourced domain model aggregate that
    specifies the routing from origin to destination, and can track what
    happens to the cargo after it has been booked.
    """

    @triggers(BookingStarted)
    def __init__(
        self,
        origin: Location,
        destination: Location,
        arrival_deadline: datetime,
    ):
        self._origin: Location = origin
        self._destination: Location = destination
        self._arrival_deadline: datetime = arrival_deadline
        self._transport_status: str = "NOT_RECEIVED"
        self._routing_status: str = "NOT_ROUTED"
        self._is_misdirected: bool = False
        self._estimated_time_of_arrival: datetime | None = None
        self._next_expected_activity: NextExpectedActivity = None
        self._route: Itinerary | None = None
        self._last_known_location: Location | None = None
        self._current_voyage_number: str | None = None

    @property
    def origin(self) -> Location:
        return self._origin

    @property
    def destination(self) -> Location:
        return self._destination

    @property
    def arrival_deadline(self) -> datetime:
        return self._arrival_deadline

    @property
    def transport_status(self) -> str:
        return self._transport_status

    @property
    def routing_status(self) -> str:
        return self._routing_status

    @property
    def is_misdirected(self) -> bool:
        return self._is_misdirected

    @property
    def estimated_time_of_arrival(
        self,
    ) -> datetime | None:
        return self._estimated_time_of_arrival

    @property
    def next_expected_activity(self) -> NextExpectedActivity:
        return self._next_expected_activity

    @property
    def route(self) -> Itinerary | None:
        return self._route

    @property
    def last_known_location(self) -> Location | None:
        return self._last_known_location

    @property
    def current_voyage_number(self) -> str | None:
        return self._current_voyage_number

    @classmethod
    def new_booking(
        cls,
        origin: Location,
        destination: Location,
        arrival_deadline: datetime,
    ) -> Cargo:
        return Cargo(
            origin=origin, destination=destination, arrival_deadline=arrival_deadline
        )

    @triggers(DestinationChanged)
    def change_destination(self, destination: Location) -> None:
        self._destination = destination

    @triggers(RouteAssigned)
    def assign_route(self, route: Itinerary) -> None:
        self._route = route
        self._routing_status = "ROUTED"
        self._estimated_time_of_arrival = datetime_now_with_tzinfo() + timedelta(
            weeks=1
        )
        self._next_expected_activity = (HandlingActivity.RECEIVE, self.origin, "")
        self._is_misdirected = False

    @triggers(HandlingEventRegistered)
    def register_handling_event(
        self,
        tracking_id: str,
        voyage_number: str | None,
        location: Location,
        handling_activity: HandlingActivity,
    ) -> None:
        assert self.route is not None
        if handling_activity == HandlingActivity.RECEIVE:
            self._transport_status = "IN_PORT"
            self._last_known_location = location
            self._next_expected_activity = (
                HandlingActivity.LOAD,
                location,
                self.route.legs[0].voyage_number,
            )
        elif handling_activity == HandlingActivity.LOAD:
            self._transport_status = "ONBOARD_CARRIER"
            self._current_voyage_number = voyage_number
            for leg in self.route.legs:
                if leg.origin == location.value and leg.voyage_number == voyage_number:
                    self._next_expected_activity = (
                        HandlingActivity.UNLOAD,
                        Location[leg.destination],
                        voyage_number,
                    )
                    break
            else:
                msg = (
                    f"Can't find leg with origin={location} "
                    f"and voyage_number={voyage_number}"
                )
                raise ValueError(msg)

        elif handling_activity == HandlingActivity.UNLOAD:
            self._current_voyage_number = None
            self._last_known_location = location
            self._transport_status = "IN_PORT"
            if location == self.destination:
                self._next_expected_activity = (
                    HandlingActivity.CLAIM,
                    location,
                    "",
                )
            elif location.value in [leg.destination for leg in self.route.legs]:
                for i, leg in enumerate(self.route.legs):
                    if leg.voyage_number == voyage_number:
                        next_leg: Leg = self.route.legs[i + 1]
                        assert Location[next_leg.origin] == location
                        self._next_expected_activity = (
                            HandlingActivity.LOAD,
                            location,
                            next_leg.voyage_number,
                        )
                        break
            else:
                self._is_misdirected = True
                self._next_expected_activity = None

        elif handling_activity == HandlingActivity.CLAIM:
            self._next_expected_activity = None
            self._transport_status = "CLAIMED"

        else:
            msg = f"Unsupported handling activity: {handling_activity}"
            raise ValueError(msg)
