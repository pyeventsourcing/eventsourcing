import unittest
from datetime import datetime, timedelta

from eventsourcing.domain import TZINFO
from eventsourcing.examples.cargoshipping.application import BookingApplication
from eventsourcing.examples.cargoshipping.interface import (
    BookingService,
    select_preferred_itinerary,
)


class TestBookingService(unittest.TestCase):
    def setUp(self) -> None:
        self.service = BookingService(BookingApplication())

    def test_admin_can_book_new_cargo(self) -> None:
        arrival_deadline = datetime.now(tz=TZINFO) + timedelta(weeks=3)

        cargo_id = self.service.book_new_cargo(
            origin="NLRTM",
            destination="USDAL",
            arrival_deadline=arrival_deadline,
        )

        cargo_details = self.service.get_cargo_details(cargo_id)
        self.assertTrue(cargo_details["id"])
        self.assertEqual(cargo_details["origin"], "NLRTM")
        self.assertEqual(cargo_details["destination"], "USDAL")

        self.service.change_destination(cargo_id, destination="AUMEL")
        cargo_details = self.service.get_cargo_details(cargo_id)
        self.assertEqual(cargo_details["destination"], "AUMEL")
        self.assertEqual(
            cargo_details["arrival_deadline"],
            arrival_deadline,
        )

    def test_scenario_cargo_from_hongkong_to_stockholm(
        self,
    ) -> None:
        # Test setup: A cargo should be shipped from
        # Hongkong to Stockholm, and it should arrive
        # in no more than two weeks.
        origin = "HONGKONG"
        destination = "STOCKHOLM"
        arrival_deadline = datetime.now(tz=TZINFO) + timedelta(weeks=2)

        # Use case 1: booking.

        # A new cargo is booked, and the unique tracking
        # id is assigned to the cargo.
        tracking_id = self.service.book_new_cargo(origin, destination, arrival_deadline)

        # The tracking id can be used to lookup the cargo
        # in the repository.
        # Important: The cargo, and thus the domain model,
        # is responsible for determining the status of the
        # cargo, whether it is on the right track or not
        # and so on. This is core domain logic. Tracking
        # the cargo basically amounts to presenting
        # information extracted from the cargo aggregate
        # in a suitable way.
        cargo_details = self.service.get_cargo_details(tracking_id)
        self.assertEqual(
            cargo_details["transport_status"],
            "NOT_RECEIVED",
        )
        self.assertEqual(cargo_details["routing_status"], "NOT_ROUTED")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(
            cargo_details["estimated_time_of_arrival"],
            None,
        )
        self.assertEqual(cargo_details["next_expected_activity"], None)

        # Use case 2: routing.
        #
        # A number of possible routes for this cargo is
        # requested and may be presented to the customer
        # in some way for him/her to choose from.
        # Selection could be affected by things like price
        # and time of delivery, but this test simply uses
        # an arbitrary selection to mimic that process.
        routes_details = self.service.request_possible_routes_for_cargo(tracking_id)
        route_details = select_preferred_itinerary(routes_details)

        # The cargo is then assigned to the selected
        # route, described by an itinerary.
        self.service.assign_route(tracking_id, route_details)

        cargo_details = self.service.get_cargo_details(tracking_id)
        self.assertEqual(
            cargo_details["transport_status"],
            "NOT_RECEIVED",
        )
        self.assertEqual(cargo_details["routing_status"], "ROUTED")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertTrue(cargo_details["estimated_time_of_arrival"])
        self.assertEqual(
            cargo_details["next_expected_activity"],
            ("RECEIVE", "HONGKONG"),
        )

        # Use case 3: handling

        # A handling event registration attempt will be
        # formed from parsing the data coming in as a
        # handling report either via the web service
        # interface or as an uploaded CSV file. The
        # handling event factory tries to create a
        # HandlingEvent from the attempt, and if the
        # factory decides that this is a plausible
        # handling event, it is stored. If the attempt
        # is invalid, for example if no cargo exists for
        # the specified tracking id, the attempt is
        # rejected.
        #
        # Handling begins: cargo is received in Hongkong.
        self.service.register_handling_event(tracking_id, None, "HONGKONG", "RECEIVE")
        cargo_details = self.service.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["transport_status"], "IN_PORT")
        self.assertEqual(
            cargo_details["last_known_location"],
            "HONGKONG",
        )
        self.assertEqual(
            cargo_details["next_expected_activity"],
            ("LOAD", "HONGKONG", "V1"),
        )

        # Load onto voyage V1.
        self.service.register_handling_event(tracking_id, "V1", "HONGKONG", "LOAD")
        cargo_details = self.service.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], "V1")
        self.assertEqual(
            cargo_details["last_known_location"],
            "HONGKONG",
        )
        self.assertEqual(
            cargo_details["transport_status"],
            "ONBOARD_CARRIER",
        )
        self.assertEqual(
            cargo_details["next_expected_activity"],
            ("UNLOAD", "NEWYORK", "V1"),
        )

        # Incorrectly unload in Tokyo.
        self.service.register_handling_event(tracking_id, "V1", "TOKYO", "UNLOAD")
        cargo_details = self.service.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], None)
        self.assertEqual(cargo_details["last_known_location"], "TOKYO")
        self.assertEqual(cargo_details["transport_status"], "IN_PORT")
        self.assertEqual(cargo_details["is_misdirected"], True)
        self.assertEqual(cargo_details["next_expected_activity"], None)

        # Reroute.
        routes_details = self.service.request_possible_routes_for_cargo(tracking_id)
        route_details = select_preferred_itinerary(routes_details)
        self.service.assign_route(tracking_id, route_details)

        # Load in Tokyo.
        self.service.register_handling_event(tracking_id, "V3", "TOKYO", "LOAD")
        cargo_details = self.service.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], "V3")
        self.assertEqual(cargo_details["last_known_location"], "TOKYO")
        self.assertEqual(
            cargo_details["transport_status"],
            "ONBOARD_CARRIER",
        )
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(
            cargo_details["next_expected_activity"],
            ("UNLOAD", "HAMBURG", "V3"),
        )

        # Unload in Hamburg.
        self.service.register_handling_event(tracking_id, "V3", "HAMBURG", "UNLOAD")
        cargo_details = self.service.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], None)
        self.assertEqual(cargo_details["last_known_location"], "HAMBURG")
        self.assertEqual(cargo_details["transport_status"], "IN_PORT")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(
            cargo_details["next_expected_activity"],
            ("LOAD", "HAMBURG", "V4"),
        )

        # Load in Hamburg
        self.service.register_handling_event(tracking_id, "V4", "HAMBURG", "LOAD")
        cargo_details = self.service.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], "V4")
        self.assertEqual(cargo_details["last_known_location"], "HAMBURG")
        self.assertEqual(
            cargo_details["transport_status"],
            "ONBOARD_CARRIER",
        )
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(
            cargo_details["next_expected_activity"],
            ("UNLOAD", "STOCKHOLM", "V4"),
        )

        # Unload in Stockholm
        self.service.register_handling_event(tracking_id, "V4", "STOCKHOLM", "UNLOAD")
        cargo_details = self.service.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], None)
        self.assertEqual(
            cargo_details["last_known_location"],
            "STOCKHOLM",
        )
        self.assertEqual(cargo_details["transport_status"], "IN_PORT")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(
            cargo_details["next_expected_activity"],
            ("CLAIM", "STOCKHOLM"),
        )

        # Finally, cargo is claimed in Stockholm.
        self.service.register_handling_event(tracking_id, None, "STOCKHOLM", "CLAIM")
        cargo_details = self.service.get_cargo_details(tracking_id)
        self.assertEqual(cargo_details["current_voyage_number"], None)
        self.assertEqual(
            cargo_details["last_known_location"],
            "STOCKHOLM",
        )
        self.assertEqual(cargo_details["transport_status"], "CLAIMED")
        self.assertEqual(cargo_details["is_misdirected"], False)
        self.assertEqual(cargo_details["next_expected_activity"], None)
