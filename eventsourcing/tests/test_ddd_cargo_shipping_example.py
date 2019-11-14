from datetime import datetime, timedelta
from typing import Optional
from unittest import TestCase

from eventsourcing.application.popo import PopoApplication
from eventsourcing.application.process import ProcessApplication
from eventsourcing.application.system import (
    InProcessRunner,
    SingleThreadedRunner,
    System,
)
from eventsourcing.domain.model.aggregate import BaseAggregateRoot
from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.exceptions import RepositoryKeyError


class TestDDDCargoShippingExample(TestCase):
    def setUp(self) -> None:
        self.runner = SingleThreadedRunner(
            system=System(BookingApplication),
            infrastructure_class=PopoApplication,
            setup_tables=True
        )
        self.runner.start()
        self.client = LocalClient(self.runner)

    def tearDown(self) -> None:
        self.runner.close()

    def test_admin_can_book_new_cargo(self):
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

    def test_test_cargo_from_hongkong_to_stockholm(self):
        origin = "HONGKONG"
        destination = "STOCKHOLM"
        arrival_deadline = datetime.now() + timedelta(weeks=3)

        # Use case 1: booking.
        tracking_id = self.client.book_new_cargo(origin, destination, arrival_deadline)
        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["transport_status"], "NOT_RECEIVED")
        self.assertEqual(cargo_details["routing_status"], "NOT_ROUTED")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(cargo_details["estimated_time_of_arrival"], None)
        self.assertEqual(cargo_details["next_expected_activity"], None)

        # Use case 2: routing.
        itineraries = self.client.request_possible_routes_for_cargo(tracking_id)
        itinerary = select_preferred_itinerary(itineraries)
        self.client.assign_route(tracking_id, itinerary)

        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["transport_status"], "NOT_RECEIVED")
        self.assertEqual(cargo_details["routing_status"], "ROUTED")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertTrue(cargo_details["estimated_time_of_arrival"])
        self.assertEqual(
            cargo_details["next_expected_activity"], ("RECEIVE", "HONGKONG")
        )

        # Use case 3: handling

        # Receive in Hong Kong.
        self.client.register_handling_event(tracking_id, None, "HONGKONG", "RECEIVED")
        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["transport_status"], "IN_PORT")
        self.assertEqual(cargo_details["last_known_location"], "HONGKONG")

        # Load onto voyage V1.
        self.client.register_handling_event(tracking_id, "V1", "HONGKONG", "LOADED")
        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], "V1")
        self.assertEqual(cargo_details["last_known_location"], "HONGKONG")
        self.assertEqual(cargo_details["transport_status"], "ONBOARD_CARRIER")
        self.assertEqual(
            cargo_details["next_expected_activity"], ("UNLOAD", "NEWYORK", "V1")
        )

        # Incorrectly unload in Tokyo.
        self.client.register_handling_event(tracking_id, "V1", "TOKYO", "UNLOADED")
        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], None)
        self.assertEqual(cargo_details["last_known_location"], "TOKYO")
        self.assertEqual(cargo_details["transport_status"], "IN_PORT")
        self.assertEqual(cargo_details["is_misdirected"], True)
        self.assertEqual(cargo_details["next_expected_activity"], None)

        # Reroute.
        itineraries = self.client.request_possible_routes_for_cargo(tracking_id)
        itinerary = select_preferred_itinerary(itineraries)
        self.client.assign_route(tracking_id, itinerary)

        # Load in Tokyo.
        self.client.register_handling_event(tracking_id, "V3", "TOKYO", "LOADED")

        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], "V3")
        self.assertEqual(cargo_details["last_known_location"], "TOKYO")
        self.assertEqual(cargo_details["transport_status"], "ONBOARD_CARRIER")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(
            cargo_details["next_expected_activity"], ("UNLOAD", "HAMBURG", "V3")
        )

        # Unload in Hamburg.
        self.client.register_handling_event(tracking_id, "V3", "HAMBURG", "UNLOADED")

        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], None)
        self.assertEqual(cargo_details["last_known_location"], "HAMBURG")
        self.assertEqual(cargo_details["transport_status"], "IN_PORT")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(
            cargo_details["next_expected_activity"], ("LOAD", "HAMBURG", "V4")
        )
        # Todo: How does it know which is the next voyage? Is that part of the route?

        # Load in Hamburg
        self.client.register_handling_event(tracking_id, "V4", "HAMBURG", "LOADED")

        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], "V4")
        self.assertEqual(cargo_details["last_known_location"], "HAMBURG")
        self.assertEqual(cargo_details["transport_status"], "ONBOARD_CARRIER")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(
            cargo_details["next_expected_activity"], ("UNLOAD", "STOCKHOLM", "V4")
        )

        # Unload in Stockholm
        self.client.register_handling_event(tracking_id, "V4", "STOCKHOLM", "UNLOADED")

        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], None)
        self.assertEqual(cargo_details["last_known_location"], "STOCKHOLM")
        self.assertEqual(cargo_details["transport_status"], "IN_PORT")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(
            cargo_details["next_expected_activity"], ("CLAIM", "STOCKHOLM")
        )

        # Finally, cargo is claimed in Stockholm.
        self.client.register_handling_event(tracking_id, None, "STOCKHOLM", "CLAIMED")

        cargo_details = self.client.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], None)
        self.assertEqual(cargo_details["last_known_location"], "STOCKHOLM")
        self.assertEqual(cargo_details["transport_status"], "CLAIMED")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(cargo_details["next_expected_activity"], None)


def select_preferred_itinerary(itineraries):
    return itineraries[0]


class Itinerary(object):
    def __init__(self, origin, destination, legs):
        self.origin = origin
        self.destination = destination
        self.legs = legs


class Leg(object):
    def __init__(self, origin, destination, voyage_number):
        self.origin = origin
        self.destination = destination
        self.voyage_number = voyage_number


class Cargo(BaseAggregateRoot):
    __subclassevents__ = True

    @classmethod
    def new_booking(cls, origin, destination, arrival_deadline):
        cargo = cls.__create__(
            origin=origin, destination=destination, arrival_deadline=arrival_deadline
        )
        return cargo

    def __init__(self, origin, destination, arrival_deadline, **kwargs):
        super().__init__(**kwargs)
        self._origin = origin
        self._destination = destination
        self._arrival_deadline = arrival_deadline
        self._transport_status = "NOT_RECEIVED"
        self._routing_status = "NOT_ROUTED"
        self._is_misdirected = False
        self._estimated_time_of_arrival = None
        self._next_expected_activity = None
        self._route: Optional[Itinerary] = None
        self._last_known_location = None
        self._current_voyage_number = None

    @property
    def origin(self):
        return self._origin

    @property
    def destination(self):
        return self._destination

    @property
    def arrival_deadline(self):
        return self._arrival_deadline

    @property
    def transport_status(self):
        return self._transport_status

    @property
    def routing_status(self):
        return self._routing_status

    @property
    def is_misdirected(self):
        return self._is_misdirected

    @property
    def estimated_time_of_arrival(self):
        return self._estimated_time_of_arrival

    @property
    def next_expected_activity(self):
        return self._next_expected_activity

    @property
    def last_known_location(self):
        return self._last_known_location

    @property
    def current_voyage_number(self):
        return self._current_voyage_number

    def change_destination(self, destination):
        self.__trigger_event__(self.DestinationChanged, destination=destination)

    class DestinationChanged(DomainEvent):
        def mutate(self, obj):
            assert isinstance(obj, Cargo)
            obj._destination = self.destination

        @property
        def destination(self):
            return self.__dict__["destination"]

    def assign_route(self, itinerary):
        self.__trigger_event__(self.RouteAssigned, route=itinerary)

    class RouteAssigned(DomainEvent):
        def mutate(self, obj):
            # Todo: Why is the class getting messed up by cast()???
            #  It comes out as an instance of MetaDomainEntity??
            # cargo = cast(obj, Cargo)
            # assert isinstance(cargo, Cargo), (type(cargo), Cargo)

            assert isinstance(obj, Cargo), (type(obj), Cargo)
            obj._route = self.route
            obj._routing_status = "ROUTED"
            obj._estimated_time_of_arrival = datetime.now() + timedelta(weeks=1)
            obj._next_expected_activity = ("RECEIVE", obj.origin)
            obj._is_misdirected = False

        @property
        def route(self):
            return self.__dict__["route"]

    def register_handling_event(self, tracking_id, voyage_number, location, event_name):
        self.__trigger_event__(
            self.HandlingEventRegistered,
            tracking_id=tracking_id,
            voyage_number=voyage_number,
            location=location,
            event_name=event_name,
        )

    class HandlingEventRegistered(DomainEvent):
        def mutate(self, obj):
            assert isinstance(obj, Cargo)
            if self.event_name == "RECEIVED":
                obj._transport_status = "IN_PORT"
                obj._last_known_location = self.location
            elif self.event_name == "LOADED":
                obj._transport_status = "ONBOARD_CARRIER"
                obj._current_voyage_number = self.voyage_number
                assert obj._route is not None
                for leg in obj._route.legs:
                    if leg.origin == self.location:
                        if leg.voyage_number == self.voyage_number:
                            obj._next_expected_activity = (
                                "UNLOAD",
                                leg.destination,
                                self.voyage_number,
                            )
                            break
                else:
                    raise Exception(
                        "Can't find leg with origin={} and "
                        "voyage_number={}".format(self.location, self.voyage_number)
                    )

            elif self.event_name == "UNLOADED":
                obj._current_voyage_number = None
                obj._last_known_location = self.location
                obj._transport_status = "IN_PORT"
                if self.location == obj.destination:
                    obj._next_expected_activity = ("CLAIM", self.location)
                elif self.location in [leg.destination for leg in obj._route.legs]:
                    for i, leg in enumerate(obj._route.legs):
                        if leg.voyage_number == self.voyage_number:
                            next_leg: Leg = obj._route.legs[i + 1]
                            assert next_leg.origin == self.location
                            obj._next_expected_activity = (
                                "LOAD",
                                self.location,
                                next_leg.voyage_number,
                            )
                            break
                else:
                    obj._is_misdirected = True
                    obj._next_expected_activity = None

            elif self.event_name == "CLAIMED":
                obj._next_expected_activity = None
                obj._transport_status = "CLAIMED"

            else:
                raise Exception(
                    "Unsupported handling event: {}".format(self.event_name)
                )

        @property
        def voyage_number(self):
            return self.__dict__["voyage_number"]

        @property
        def location(self):
            return self.__dict__["location"]

        @property
        def event_name(self):
            return self.__dict__["event_name"]


# Todo: More about registering routes.
class CargoNotFound(Exception):
    pass


# Todo: More about registering routes.
class BookingApplication(ProcessApplication):
    use_cache = True
    persist_event_type = Cargo.Event

    def book_new_cargo(self, origin, destination, arrival_deadline):
        cargo = Cargo.new_booking(origin, destination, arrival_deadline)
        cargo.__save__()
        return cargo.id

    def get_cargo(self, tracking_id) -> Cargo:
        try:
            entity = self.repository[tracking_id]
        except RepositoryKeyError:
            raise CargoNotFound(tracking_id)
        else:
            return entity

    def change_destination(self, cargo_id, destination):
        cargo = self.get_cargo(cargo_id)
        cargo.change_destination(destination)
        cargo.__save__()

    def request_possible_routes_for_cargo(self, tracking_id):
        cargo = self.get_cargo(tracking_id)
        from_location = cargo.last_known_location or cargo.origin
        to_location = cargo.destination
        if (from_location, to_location) == ("HONGKONG", "STOCKHOLM"):
            return [
                Itinerary(
                    origin="HONGKONG",
                    destination="STOCKHOLM",
                    legs=[
                        Leg(
                            origin="HONGKONG", destination="NEWYORK", voyage_number="V1"
                        ),
                        Leg(
                            origin="NEWYORK",
                            destination="STOCKHOLM",
                            voyage_number="V2",
                        ),
                    ],
                ),
            ]
        elif (from_location, to_location) == ("TOKYO", "STOCKHOLM"):
            return [
                Itinerary(
                    origin="TOKYO",
                    destination="STOCKHOLM",
                    legs=[
                        Leg(origin="TOKYO", destination="HAMBURG", voyage_number="V3"),
                        Leg(
                            origin="HAMBURG",
                            destination="STOCKHOLM",
                            voyage_number="V4",
                        ),
                    ],
                ),
            ]

    def assign_route(self, tracking_id, itinerary):
        cargo: Cargo = self.get_cargo(tracking_id)
        cargo.assign_route(itinerary)
        cargo.__save__()

    def register_handling_event(self, tracking_id, voyage_number, location, event_name):
        cargo: Cargo = self.get_cargo(tracking_id)
        cargo.register_handling_event(tracking_id, voyage_number, location, event_name)
        cargo.__save__()


class LocalClient(object):
    def __init__(self, runner: InProcessRunner):
        self.runner = runner
        self.bookingapplication: BookingApplication = self.runner.bookingapplication

    def book_new_cargo(self, origin, destination, arrival_deadline):
        return self.bookingapplication.book_new_cargo(
            origin, destination, arrival_deadline
        )

    def get_cargo_details(self, cargo_id):
        cargo = self.bookingapplication.get_cargo(cargo_id)
        return {
            "id": cargo.id,
            "origin": cargo.origin,
            "destination": cargo.destination,
            "arrival_deadline": cargo.arrival_deadline,
            "transport_status": cargo.transport_status,
            "routing_status": cargo.routing_status,
            "is_misdirected": cargo.is_misdirected,
            "estimated_time_of_arrival": cargo.estimated_time_of_arrival,
            "next_expected_activity": cargo.next_expected_activity,
            "last_known_location": cargo.last_known_location,
            "current_voyage_number": cargo.current_voyage_number,
        }

    def change_destination(self, cargo_id, destination):
        self.bookingapplication.change_destination(cargo_id, destination)

    def request_possible_routes_for_cargo(self, tracking_id):
        return self.bookingapplication.request_possible_routes_for_cargo(tracking_id)

    def assign_route(self, tracking_id, itinerary):
        self.bookingapplication.assign_route(tracking_id, itinerary)

    def register_handling_event(self, tracking_id, param, location, event_name):
        self.bookingapplication.register_handling_event(
            tracking_id, param, location, event_name
        )
