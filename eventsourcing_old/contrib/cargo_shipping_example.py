"""
This example follows the original Cargo Shipping example
that figures in the DDD book, as coded in the "DDD Sample"
project. As it says on the project website, "This project is a
joint effort by Eric Evans' company Domain Language and
the Swedish software consulting company Citerus.

  -  http://dddsample.sourceforge.net/

"One of the most requested aids to coming up to speed on DDD
has been a running example application. Starting from a simple
set of functions and a model based on the cargo example used
in Eric Evans' book, we have built a running application with
which to demonstrate a practical implementation of the building
block patterns as well as illustrate the impact of aggregates
and bounded contexts."

"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union
from unittest import TestCase
from uuid import UUID

from eventsourcing.application.process import ProcessApplication
from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.domain.model.aggregate import (
    AggregateRoot,
    TAggregate,
    TAggregateEvent,
)
from eventsourcing.system.definition import System
from eventsourcing.system.runner import InProcessRunner, SingleThreadedRunner


# Locations in the world.
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
    def __init__(self, origin: str, destination: str, voyage_number: str):
        self.origin: str = origin
        self.destination: str = destination
        self.voyage_number: str = voyage_number


# Itinerary.
class Itinerary(object):
    def __init__(self, origin: str, destination: str, legs: List[Leg]):
        self.origin = origin
        self.destination = destination
        self.legs = legs


# Some routes from one location to another.
REGISTERED_ROUTES = {
    ("HONGKONG", "STOCKHOLM"): [
        Itinerary(
            origin="HONGKONG",
            destination="STOCKHOLM",
            legs=[
                Leg(origin="HONGKONG", destination="NEWYORK", voyage_number="V1"),
                Leg(origin="NEWYORK", destination="STOCKHOLM", voyage_number="V2"),
            ],
        )
    ],
    ("TOKYO", "STOCKHOLM"): [
        Itinerary(
            origin="TOKYO",
            destination="STOCKHOLM",
            legs=[
                Leg(origin="TOKYO", destination="HAMBURG", voyage_number="V3"),
                Leg(origin="HAMBURG", destination="STOCKHOLM", voyage_number="V4"),
            ],
        )
    ],
}


# Handling activities.
class HandlingActivity(Enum):
    RECEIVE = "RECEIVE"
    LOAD = "LOAD"
    UNLOAD = "UNLOAD"
    CLAIM = "CLAIM"


# Custom static types.
NextExpectedActivity = Optional[
    Union[Tuple[HandlingActivity, Location], Tuple[HandlingActivity, Location, str]]
]
CargoDetails = Dict[str, Optional[Union[str, bool, datetime, Tuple]]]
LegDetails = Dict[str, str]
ItineraryDetails = Dict[str, Union[str, List[LegDetails]]]

# Type variable for Cargo aggregate class.
T_cargo = TypeVar("T_cargo", bound="Cargo")


# Custom aggregate root class.
class Aggregate(AggregateRoot):
    __subclassevents__ = True


# The Cargo aggregate is an event sourced domain model aggregate that
# specifies the routing from origin to destination, and can track what
# happens to the cargo after it has been booked.


class Cargo(Aggregate):
    @classmethod
    def new_booking(
        cls: Type[T_cargo],
        origin: Location,
        destination: Location,
        arrival_deadline: datetime,
    ) -> T_cargo:
        assert issubclass(cls, Cargo)  # For PyCharm navigation.
        return cls.__create__(
            origin=origin, destination=destination, arrival_deadline=arrival_deadline
        )

    def __init__(
        self,
        origin: Location,
        destination: Location,
        arrival_deadline: datetime,
        **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self._origin: Location = origin
        self._destination: Location = destination
        self._arrival_deadline: datetime = arrival_deadline
        self._transport_status: str = "NOT_RECEIVED"
        self._routing_status: str = "NOT_ROUTED"
        self._is_misdirected: bool = False
        self._estimated_time_of_arrival: Optional[datetime] = None
        self._next_expected_activity: NextExpectedActivity = None
        self._route: Optional[Itinerary] = None
        self._last_known_location: Optional[Location] = None
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
    def estimated_time_of_arrival(self) -> Optional[datetime]:
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

    class Event(Aggregate.Event):
        pass

    def change_destination(self, destination: Location) -> None:
        self.__trigger_event__(self.DestinationChanged, destination=destination)

    class DestinationChanged(Event):
        def mutate(self, obj: "Cargo") -> None:
            obj._destination = self.destination

        @property
        def destination(self) -> Location:
            return self.__dict__["destination"]

    def assign_route(self, itinerary: Itinerary) -> None:
        self.__trigger_event__(self.RouteAssigned, route=itinerary)

    class RouteAssigned(Event):
        def mutate(self, obj: "Cargo") -> None:
            obj._route = self.route
            obj._routing_status = "ROUTED"
            obj._estimated_time_of_arrival = datetime.now() + timedelta(weeks=1)
            obj._next_expected_activity = (HandlingActivity.RECEIVE, obj.origin)
            obj._is_misdirected = False

        @property
        def route(self) -> Itinerary:
            return self.__dict__["route"]

    def register_handling_event(
        self,
        tracking_id: UUID,
        voyage_number: Optional[str],
        location: Location,
        handling_activity: HandlingActivity,
    ) -> None:
        self.__trigger_event__(
            self.HandlingEventRegistered,
            tracking_id=tracking_id,
            voyage_number=voyage_number,
            location=location,
            handling_activity=handling_activity,
        )

    class HandlingEventRegistered(Event):
        def mutate(self, obj: "Cargo") -> None:
            assert obj.route is not None
            if self.handling_activity == HandlingActivity.RECEIVE:
                obj._transport_status = "IN_PORT"
                obj._last_known_location = self.location
                obj._next_expected_activity = (
                    HandlingActivity.LOAD,
                    self.location,
                    obj.route.legs[0].voyage_number,
                )
            elif self.handling_activity == HandlingActivity.LOAD:
                obj._transport_status = "ONBOARD_CARRIER"
                obj._current_voyage_number = self.voyage_number
                for leg in obj.route.legs:
                    if leg.origin == self.location.value:
                        if leg.voyage_number == self.voyage_number:
                            obj._next_expected_activity = (
                                HandlingActivity.UNLOAD,
                                Location[leg.destination],
                                self.voyage_number,
                            )
                            break
                else:
                    raise Exception(
                        "Can't find leg with origin={} and "
                        "voyage_number={}".format(self.location, self.voyage_number)
                    )

            elif self.handling_activity == HandlingActivity.UNLOAD:
                obj._current_voyage_number = None
                obj._last_known_location = self.location
                obj._transport_status = "IN_PORT"
                if self.location == obj.destination:
                    obj._next_expected_activity = (
                        HandlingActivity.CLAIM,
                        self.location,
                    )
                elif self.location.value in [leg.destination for leg in obj.route.legs]:
                    for i, leg in enumerate(obj.route.legs):
                        if leg.voyage_number == self.voyage_number:
                            next_leg: Leg = obj.route.legs[i + 1]
                            assert Location[next_leg.origin] == self.location
                            obj._next_expected_activity = (
                                HandlingActivity.LOAD,
                                self.location,
                                next_leg.voyage_number,
                            )
                            break
                else:
                    obj._is_misdirected = True
                    obj._next_expected_activity = None

            elif self.handling_activity == HandlingActivity.CLAIM:
                obj._next_expected_activity = None
                obj._transport_status = "CLAIMED"

            else:
                raise Exception(
                    "Unsupported handling event: {}".format(self.handling_activity)
                )

        @property
        def voyage_number(self) -> str:
            return self.__dict__["voyage_number"]

        @property
        def location(self) -> Location:
            return self.__dict__["location"]

        @property
        def handling_activity(self) -> str:
            return self.__dict__["handling_activity"]


# Cargo aggregates exist within an application, which
# provides "application service" methods for clients.
class BookingApplication(ProcessApplication[TAggregate, TAggregateEvent]):
    persist_event_type = Cargo.Event

    @staticmethod
    def book_new_cargo(
        origin: Location, destination: Location, arrival_deadline: datetime
    ) -> UUID:
        cargo = Cargo.new_booking(origin, destination, arrival_deadline)
        cargo.__save__()
        return cargo.id

    def change_destination(self, tracking_id: UUID, destination: Location) -> None:
        cargo = self.get_cargo(tracking_id)
        cargo.change_destination(destination)
        cargo.__save__()

    def request_possible_routes_for_cargo(self, tracking_id: UUID) -> List[Itinerary]:
        cargo = self.get_cargo(tracking_id)
        from_location = (cargo.last_known_location or cargo.origin).value
        to_location = cargo.destination.value
        try:
            possible_routes = REGISTERED_ROUTES[(from_location, to_location)]
        except KeyError:
            raise Exception(
                "Can't find routes from {} to {}".format(from_location, to_location)
            )

        return possible_routes

    def assign_route(self, tracking_id: UUID, itinerary: Itinerary) -> None:
        cargo = self.get_cargo(tracking_id)
        cargo.assign_route(itinerary)
        cargo.__save__()

    def register_handling_event(
        self,
        tracking_id: UUID,
        voyage_number: Optional[str],
        location: Location,
        handing_activity: HandlingActivity,
    ) -> None:
        cargo = self.get_cargo(tracking_id)
        cargo.register_handling_event(
            tracking_id, voyage_number, location, handing_activity
        )
        cargo.__save__()

    def get_cargo(self, tracking_id: UUID) -> Cargo:
        cargo = self.repository.get_instance_of(Cargo, tracking_id)
        if cargo is None:
            raise Exception("Cargo not found: {}".format(tracking_id))
        else:
            return cargo


# The application services are presented in a client interface that
# deals with simple types of object (str, bool, datetime).
class LocalClient(object):
    def __init__(self, runner: InProcessRunner):
        self.runner: InProcessRunner = runner
        self.booking_application = self.runner.get(BookingApplication)

    def book_new_cargo(
        self, origin: str, destination: str, arrival_deadline: datetime
    ) -> str:
        tracking_id = self.booking_application.book_new_cargo(
            Location[origin], Location[destination], arrival_deadline
        )
        return str(tracking_id)

    def get_cargo_details(self, tracking_id: str) -> CargoDetails:
        cargo = self.booking_application.get_cargo(UUID(tracking_id))

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
        self.booking_application.change_destination(
            UUID(tracking_id), Location[destination]
        )

    def request_possible_routes_for_cargo(self, tracking_id: str) -> List[dict]:
        routes = self.booking_application.request_possible_routes_for_cargo(
            UUID(tracking_id)
        )
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

    def assign_route(self, tracking_id: str, route_details: ItineraryDetails) -> None:
        routes = self.booking_application.request_possible_routes_for_cargo(
            UUID(tracking_id)
        )
        for route in routes:
            if route_details == self.dict_from_itinerary(route):
                self.booking_application.assign_route(UUID(tracking_id), route)

    def register_handling_event(
        self,
        tracking_id: str,
        voyage_number: Optional[str],
        location: str,
        handling_activity: str,
    ) -> None:
        self.booking_application.register_handling_event(
            UUID(tracking_id),
            voyage_number,
            Location[location],
            HandlingActivity[handling_activity],
        )


# Stub function that picks an itineraries from a list of possible itineraries.
def select_preferred_itinerary(itineraries: List[ItineraryDetails]) -> ItineraryDetails:
    return itineraries[0]


class TestDDDCargoShippingExample(TestCase):
    def setUp(self) -> None:
        self.runner = SingleThreadedRunner(
            system=System(BookingApplication),
            infrastructure_class=SQLAlchemyApplication,
            setup_tables=True,
        )
        self.runner.start()
        self.client = LocalClient(self.runner)

    def tearDown(self) -> None:
        self.runner.close()

    def test_admin_can_book_new_cargo(self) -> None:
        arrival_deadline = datetime.now() + timedelta(weeks=3)

        cargo_id = self.client.book_new_cargo(
            origin="NLRTM", destination="USDAL", arrival_deadline=arrival_deadline
        )

        cargo_details = self.client.get_cargo_details(cargo_id)
        self.assertTrue(cargo_details["id"])
        self.assertEqual(cargo_details["origin"], "NLRTM")
        self.assertEqual(cargo_details["destination"], "USDAL")

        self.client.change_destination(cargo_id, destination="AUMEL")
        cargo_details = self.client.get_cargo_details(cargo_id)
        self.assertEqual(cargo_details["destination"], "AUMEL")
        self.assertEqual(cargo_details["arrival_deadline"], arrival_deadline)

    def test_scenario_cargo_from_hongkong_to_stockholm(self) -> None:
        # Test setup: A cargo should be shipped from Hongkong to Stockholm,
        # and it should arrive in no more than two weeks.
        origin = "HONGKONG"
        destination = "STOCKHOLM"
        arrival_deadline = datetime.now() + timedelta(weeks=2)

        # Use case 1: booking.

        # A new cargo is booked, and the unique tracking id is assigned to the cargo.
        tracking_id = self.client.book_new_cargo(origin, destination, arrival_deadline)

        # The tracking id can be used to lookup the cargo in the repository.
        # Important: The cargo, and thus the domain model, is responsible for
        # determining the status of the cargo, whether it is on the right track
        # or not and so on. This is core domain logic. Tracking the cargo basically
        # amounts to presenting information extracted from the cargo aggregate in a
        # suitable way.
        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["transport_status"], "NOT_RECEIVED")
        self.assertEqual(cargo_details["routing_status"], "NOT_ROUTED")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(cargo_details["estimated_time_of_arrival"], None)
        self.assertEqual(cargo_details["next_expected_activity"], None)

        # Use case 2: routing.
        #
        # A number of possible routes for this cargo is requested and may be
        # presented to the customer in some way for him/her to choose from.
        # Selection could be affected by things like price and time of delivery,
        # but this test simply uses an arbitrary selection to mimic that process.
        routes_details = self.client.request_possible_routes_for_cargo(tracking_id)
        route_details = select_preferred_itinerary(routes_details)

        # The cargo is then assigned to the selected route, described by an itinerary.
        self.client.assign_route(tracking_id, route_details)

        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["transport_status"], "NOT_RECEIVED")
        self.assertEqual(cargo_details["routing_status"], "ROUTED")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertTrue(cargo_details["estimated_time_of_arrival"])
        self.assertEqual(
            cargo_details["next_expected_activity"], ("RECEIVE", "HONGKONG")
        )

        # Use case 3: handling

        # A handling event registration attempt will be formed from parsing
        # the data coming in as a handling report either via the web service
        # interface or as an uploaded CSV file. The handling event factory
        # tries to create a HandlingEvent from the attempt, and if the factory
        # decides that this is a plausible handling event, it is stored.
        # If the attempt is invalid, for example if no cargo exists for the
        # specfied tracking id, the attempt is rejected.
        #
        # Handling begins: cargo is received in Hongkong.
        self.client.register_handling_event(tracking_id, None, "HONGKONG", "RECEIVE")
        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["transport_status"], "IN_PORT")
        self.assertEqual(cargo_details["last_known_location"], "HONGKONG")
        self.assertEqual(
            cargo_details["next_expected_activity"], ("LOAD", "HONGKONG", "V1")
        )

        # Load onto voyage V1.
        self.client.register_handling_event(tracking_id, "V1", "HONGKONG", "LOAD")
        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], "V1")
        self.assertEqual(cargo_details["last_known_location"], "HONGKONG")
        self.assertEqual(cargo_details["transport_status"], "ONBOARD_CARRIER")
        self.assertEqual(
            cargo_details["next_expected_activity"], ("UNLOAD", "NEWYORK", "V1")
        )

        # Incorrectly unload in Tokyo.
        self.client.register_handling_event(tracking_id, "V1", "TOKYO", "UNLOAD")
        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], None)
        self.assertEqual(cargo_details["last_known_location"], "TOKYO")
        self.assertEqual(cargo_details["transport_status"], "IN_PORT")
        self.assertEqual(cargo_details["is_misdirected"], True)
        self.assertEqual(cargo_details["next_expected_activity"], None)

        # Reroute.
        routes_details = self.client.request_possible_routes_for_cargo(tracking_id)
        route_details = select_preferred_itinerary(routes_details)
        self.client.assign_route(tracking_id, route_details)

        # Load in Tokyo.
        self.client.register_handling_event(tracking_id, "V3", "TOKYO", "LOAD")
        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], "V3")
        self.assertEqual(cargo_details["last_known_location"], "TOKYO")
        self.assertEqual(cargo_details["transport_status"], "ONBOARD_CARRIER")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(
            cargo_details["next_expected_activity"], ("UNLOAD", "HAMBURG", "V3")
        )

        # Unload in Hamburg.
        self.client.register_handling_event(tracking_id, "V3", "HAMBURG", "UNLOAD")
        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], None)
        self.assertEqual(cargo_details["last_known_location"], "HAMBURG")
        self.assertEqual(cargo_details["transport_status"], "IN_PORT")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(
            cargo_details["next_expected_activity"], ("LOAD", "HAMBURG", "V4")
        )

        # Load in Hamburg
        self.client.register_handling_event(tracking_id, "V4", "HAMBURG", "LOAD")
        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], "V4")
        self.assertEqual(cargo_details["last_known_location"], "HAMBURG")
        self.assertEqual(cargo_details["transport_status"], "ONBOARD_CARRIER")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(
            cargo_details["next_expected_activity"], ("UNLOAD", "STOCKHOLM", "V4")
        )

        # Unload in Stockholm
        self.client.register_handling_event(tracking_id, "V4", "STOCKHOLM", "UNLOAD")
        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], None)
        self.assertEqual(cargo_details["last_known_location"], "STOCKHOLM")
        self.assertEqual(cargo_details["transport_status"], "IN_PORT")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(
            cargo_details["next_expected_activity"], ("CLAIM", "STOCKHOLM")
        )

        # Finally, cargo is claimed in Stockholm.
        self.client.register_handling_event(tracking_id, None, "STOCKHOLM", "CLAIM")
        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], None)
        self.assertEqual(cargo_details["last_known_location"], "STOCKHOLM")
        self.assertEqual(cargo_details["transport_status"], "CLAIMED")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(cargo_details["next_expected_activity"], None)
