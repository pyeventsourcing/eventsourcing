from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)
from uuid import UUID, uuid4

# Locations in the world.
from eventsourcing.domain import Aggregate


class Location(Enum):
    HAMBURG = "HAMBURG"
    HONGKONG = "HONGKONG"
    NEWYORK = "NEWYORK"
    STOCKHOLM = "STOCKHOLM"
    TOKYO = "TOKYO"

    NLRTM = "NLRTM"
    USDAL = "USDAL"
    AUMEL = "AUMEL"


# Leg of an Itinerary.
class Leg(object):
    def __init__(
        self,
        origin: str,
        destination: str,
        voyage_number: str,
    ):
        self.origin: str = origin
        self.destination: str = destination
        self.voyage_number: str = voyage_number


# Itinerary.
class Itinerary(object):
    def __init__(
        self,
        origin: str,
        destination: str,
        legs: Tuple[Leg, ...],
    ):
        self.origin = origin
        self.destination = destination
        self.legs = legs


# Handling activities.
class HandlingActivity(Enum):
    RECEIVE = "RECEIVE"
    LOAD = "LOAD"
    UNLOAD = "UNLOAD"
    CLAIM = "CLAIM"


# Custom static types.
CargoDetails = Dict[
    str, Optional[Union[str, bool, datetime, Tuple]]
]

LegDetails = Dict[str, str]

ItineraryDetails = Dict[str, Union[str, List[LegDetails]]]

NextExpectedActivity = Optional[
    Union[
        Tuple[HandlingActivity, Location],
        Tuple[HandlingActivity, Location, str],
    ]
]


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


# The Cargo aggregate is an event-sourced domain model aggregate that
# specifies the routing from origin to destination, and can track what
# happens to the cargo after it has been booked.
class Cargo(Aggregate):
    class Event(Aggregate.Event):
        pass

    @classmethod
    def new_booking(
        cls,
        origin: Location,
        destination: Location,
        arrival_deadline: datetime,
    ) -> "Cargo":
        return cls._create_(
            event_class=Cargo.BookingStarted,
            uuid=uuid4(),
            origin=origin,
            destination=destination,
            arrival_deadline=arrival_deadline,
        )

    class BookingStarted(Aggregate.Created):
        origin: Location
        destination: Location
        arrival_deadline: datetime

    def __init__(
        self,
        origin: Location,
        destination: Location,
        arrival_deadline: datetime,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._origin: Location = origin
        self._destination: Location = destination
        self._arrival_deadline: datetime = arrival_deadline
        self._transport_status: str = "NOT_RECEIVED"
        self._routing_status: str = "NOT_ROUTED"
        self._is_misdirected: bool = False
        self._estimated_time_of_arrival: Optional[
            datetime
        ] = None
        self._next_expected_activity: NextExpectedActivity = (
            None
        )
        self._route: Optional[Itinerary] = None
        self._last_known_location: Optional[
            Location
        ] = None
        self._current_voyage_number: Optional[str] = None

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
    ) -> Optional[datetime]:
        return self._estimated_time_of_arrival

    @property
    def next_expected_activity(self) -> Optional[Tuple]:
        return self._next_expected_activity

    @property
    def route(self) -> Optional[Itinerary]:
        return self._route

    @property
    def last_known_location(self) -> Optional[Location]:
        return self._last_known_location

    @property
    def current_voyage_number(self) -> Optional[str]:
        return self._current_voyage_number

    def change_destination(
        self, destination: Location
    ) -> None:
        self._trigger_(
            self.DestinationChanged,
            destination=destination,
        )

    class DestinationChanged(Aggregate.Event):
        destination: Location

        def apply(self, obj: "Cargo") -> None:
            obj._destination = self.destination

    def assign_route(self, itinerary: Itinerary) -> None:
        self._trigger_(self.RouteAssigned, route=itinerary)

    class RouteAssigned(Event):
        route: Itinerary

        def apply(self, obj: "Cargo") -> None:
            obj._route = self.route
            obj._routing_status = "ROUTED"
            obj._estimated_time_of_arrival = (
                datetime.now() + timedelta(weeks=1)
            )
            obj._next_expected_activity = (
                HandlingActivity.RECEIVE,
                obj.origin,
            )
            obj._is_misdirected = False

    def register_handling_event(
        self,
        tracking_id: UUID,
        voyage_number: Optional[str],
        location: Location,
        handling_activity: HandlingActivity,
    ) -> None:
        self._trigger_(
            self.HandlingEventRegistered,
            tracking_id=tracking_id,
            voyage_number=voyage_number,
            location=location,
            handling_activity=handling_activity,
        )

    class HandlingEventRegistered(Event):
        tracking_id: UUID
        voyage_number: str
        location: Location
        handling_activity: str

        def apply(self, obj: "Cargo") -> None:
            assert obj.route is not None
            if (
                self.handling_activity
                == HandlingActivity.RECEIVE
            ):
                obj._transport_status = "IN_PORT"
                obj._last_known_location = self.location
                obj._next_expected_activity = (
                    HandlingActivity.LOAD,
                    self.location,
                    obj.route.legs[0].voyage_number,
                )
            elif (
                self.handling_activity
                == HandlingActivity.LOAD
            ):
                obj._transport_status = "ONBOARD_CARRIER"
                obj._current_voyage_number = (
                    self.voyage_number
                )
                for leg in obj.route.legs:
                    if leg.origin == self.location.value:
                        if (
                            leg.voyage_number
                            == self.voyage_number
                        ):
                            obj._next_expected_activity = (
                                HandlingActivity.UNLOAD,
                                Location[leg.destination],
                                self.voyage_number,
                            )
                            break
                else:
                    raise Exception(
                        "Can't find leg with origin={} and "
                        "voyage_number={}".format(
                            self.location,
                            self.voyage_number,
                        )
                    )

            elif (
                self.handling_activity
                == HandlingActivity.UNLOAD
            ):
                obj._current_voyage_number = None
                obj._last_known_location = self.location
                obj._transport_status = "IN_PORT"
                if self.location == obj.destination:
                    obj._next_expected_activity = (
                        HandlingActivity.CLAIM,
                        self.location,
                    )
                elif self.location.value in [
                    leg.destination
                    for leg in obj.route.legs
                ]:
                    for i, leg in enumerate(
                        obj.route.legs
                    ):
                        if (
                            leg.voyage_number
                            == self.voyage_number
                        ):
                            next_leg: Leg = obj.route.legs[
                                i + 1
                            ]
                            assert (
                                Location[next_leg.origin]
                                == self.location
                            )
                            obj._next_expected_activity = (
                                HandlingActivity.LOAD,
                                self.location,
                                next_leg.voyage_number,
                            )
                            break
                else:
                    obj._is_misdirected = True
                    obj._next_expected_activity = None

            elif (
                self.handling_activity
                == HandlingActivity.CLAIM
            ):
                obj._next_expected_activity = None
                obj._transport_status = "CLAIMED"

            else:
                raise Exception(
                    "Unsupported handling event: {}".format(
                        self.handling_activity
                    )
                )
