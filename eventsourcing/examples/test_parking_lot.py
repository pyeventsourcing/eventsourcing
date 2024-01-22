"""
After Ed Blackburn's https://github.com/edblackburn/parking-lot/.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Type, cast
from unittest import TestCase
from uuid import NAMESPACE_URL, UUID, uuid5

from eventsourcing.application import AggregateNotFoundError, Application
from eventsourcing.domain import Aggregate, triggers
from eventsourcing.system import NotificationLogReader


@dataclass
class LicencePlate:
    number: str
    regex = re.compile("^[0-9]{3}-[0-9]{3}$")

    def __post_init__(self) -> None:
        if not bool(self.regex.match(self.number)):
            raise ValueError


@dataclass
class Booking:
    start: datetime
    finish: datetime


class Product:
    delta = timedelta()

    @classmethod
    def calc_finish(cls, start: datetime) -> datetime:
        return start + cls.delta


class EndOfDay(Product):
    delta = timedelta(days=1, seconds=-1)


class EndOfWeek(Product):
    delta = timedelta(days=7, seconds=-1)


class Vehicle(Aggregate):
    class Event(Aggregate.Event):
        pass

    class Registered(Event, Aggregate.Created):
        licence_plate_number: str

    class Booked(Event):
        start: datetime
        finish: datetime

    class Unbooked(Event):
        when: datetime

    @triggers(Registered)
    def __init__(self, licence_plate_number: str):
        self.licence_plate_number = licence_plate_number
        self.bookings: List[Booking] = []
        self.inspection_failures: List[datetime] = []

    @triggers(Booked)
    def book(self, start: datetime, finish: datetime) -> None:
        self.bookings.append(Booking(start, finish))

    @triggers(Unbooked)
    def fail_inspection(self, when: datetime) -> None:
        self.inspection_failures.append(when)

    @property
    def licence_plate(self) -> LicencePlate:
        return LicencePlate(self.licence_plate_number)

    def inspect(self, when: datetime) -> None:
        for booking in self.bookings:
            if booking.start < when < booking.finish:
                break
        else:
            self.fail_inspection(when)

    @staticmethod
    def create_id(licence_plate_number: str) -> UUID:
        return uuid5(NAMESPACE_URL, f"/licence_plate_numbers/{licence_plate_number}")


class ParkingLot(Application):
    def book(self, licence_plate: LicencePlate, product: Type[Product]) -> None:
        try:
            vehicle = self.get_vehicle(licence_plate)
        except AggregateNotFoundError:
            vehicle = Vehicle(licence_plate.number)
        start = Vehicle.Event.create_timestamp()
        finish = product.calc_finish(start)
        vehicle.book(start=start, finish=finish)
        self.save(vehicle)

    def inspect(self, licence_plate: LicencePlate, when: datetime) -> None:
        vehicle = self.get_vehicle(licence_plate)
        vehicle.inspect(when)
        self.save(vehicle)

    def get_vehicle(self, licence_plate: LicencePlate) -> Vehicle:
        return cast(
            Vehicle, self.repository.get(Vehicle.create_id(licence_plate.number))
        )


class TestParkingLot(TestCase):
    def test_licence_plate(self) -> None:
        # Valid.
        licence_plate = LicencePlate("123-123")
        self.assertIsInstance(licence_plate, LicencePlate)
        self.assertEqual(licence_plate.number, "123-123")

        # Invalid.
        with self.assertRaises(ValueError):
            LicencePlate("abcdef")

    def test_parking_lot(self) -> None:
        # Construct the application object to use an SQLite database.
        app = ParkingLot(
            env={
                "PERSISTENCE_MODULE": "eventsourcing.sqlite",
                "SQLITE_DBNAME": ":memory:",
            }
        )

        # Create a valid licence plate.
        licence_plate = LicencePlate("123-123")

        # Book unregistered vehicle.
        app.book(licence_plate, EndOfDay)

        # Check vehicle state.
        vehicle = app.get_vehicle(licence_plate)
        self.assertEqual(vehicle.licence_plate, licence_plate)
        self.assertEqual(len(vehicle.bookings), 1)
        self.assertEqual(len(vehicle.inspection_failures), 0)
        booking1 = vehicle.bookings[-1]

        # Book registered vehicle.
        app.book(licence_plate, EndOfWeek)

        # Check vehicle state.
        vehicle = app.get_vehicle(licence_plate)
        self.assertEqual(len(vehicle.bookings), 2)
        self.assertEqual(len(vehicle.inspection_failures), 0)
        booking2 = vehicle.bookings[-1]

        # Inspect whilst has booking.
        app.inspect(licence_plate, Vehicle.Event.create_timestamp())

        # Check vehicle state.
        vehicle = app.get_vehicle(licence_plate)
        self.assertEqual(len(vehicle.bookings), 2)
        self.assertEqual(len(vehicle.inspection_failures), 0)

        # Inspect after bookings expired.
        inspected_on = Vehicle.Event.create_timestamp() + timedelta(days=10)
        app.inspect(licence_plate, inspected_on)

        # Check vehicle state.
        vehicle = app.get_vehicle(licence_plate)
        self.assertEqual(len(vehicle.bookings), 2)
        self.assertEqual(len(vehicle.inspection_failures), 1)

        # Check all domain events in bounded context.
        notifications = NotificationLogReader(app.notification_log).read(start=1)
        domain_events = [app.mapper.to_domain_event(n) for n in notifications]
        self.assertEqual(len(domain_events), 4)

        vehicle1_id = Vehicle.create_id("123-123")
        event0 = domain_events[0]
        assert isinstance(event0, Vehicle.Registered)
        self.assertEqual(event0.originator_id, vehicle1_id)
        self.assertEqual(event0.originator_version, 1)
        self.assertEqual(event0.licence_plate_number, "123-123")

        event1 = domain_events[1]
        assert isinstance(event1, Vehicle.Booked)
        self.assertEqual(event1.originator_id, vehicle1_id)
        self.assertEqual(event1.originator_version, 2)
        self.assertEqual(event1.start, booking1.start)
        self.assertEqual(event1.finish, booking1.finish)

        event2 = domain_events[2]
        assert isinstance(event2, Vehicle.Booked)
        self.assertEqual(event2.originator_id, vehicle1_id)
        self.assertEqual(event2.originator_version, 3)
        self.assertEqual(event2.start, booking2.start)
        self.assertEqual(event2.finish, booking2.finish)

        event3 = domain_events[3]
        assert isinstance(event3, Vehicle.Unbooked)
        self.assertEqual(event3.originator_id, vehicle1_id)
        self.assertEqual(event3.originator_version, 4)
        self.assertEqual(event3.when, inspected_on)
