from datetime import datetime, timedelta
from typing import Optional, cast
from unittest import TestCase

from eventsourcing.application.popo import PopoApplication
from eventsourcing.application.process import ProcessApplication
from eventsourcing.application.system import (
    InProcessRunner,
    SingleThreadedRunner,
    System,
)
from eventsourcing.domain.model.aggregate import BaseAggregateRoot
from eventsourcing.domain.model.decorators import subclassevents
from eventsourcing.domain.model.events import DomainEvent
from eventsourcing.exceptions import RepositoryKeyError


class TestDDDCargoShippingExample(TestCase):
    def test_admin_can_book_new_cargo(self):
        system = System(BookingApplication, IncidentLoggingApplication)
        runner = SingleThreadedRunner(system, PopoApplication)
        admin_client = LocalAdminClient(runner)
        arrival_deadline = datetime.now() + timedelta(weeks=3)
        cargo_id = admin_client.book_new_cargo(
            origin="NLRTM", destination="USDAL", arrival_deadline=arrival_deadline
        )
        cargo_details = admin_client.get_cargo_details(cargo_id)

        self.assertTrue(cargo_details["id"])
        self.assertEqual(cargo_details["origin"], "NLRTM")
        self.assertEqual(cargo_details["destination"], "USDAL")

        admin_client.change_destination(cargo_id, destination="AUMEL")
        cargo_details = admin_client.get_cargo_details(cargo_id)
        self.assertEqual(cargo_details["destination"], "AUMEL")
        self.assertEqual(cargo_details["arrival_deadline"], arrival_deadline)


    def test_cargo_event_classes(self):
        self.assertTrue('Event' in Cargo.__dict__)
        self.assertTrue(issubclass(Cargo.DestinationChanged, Cargo.Event))

class LocalAdminClient(object):
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
        }

    def change_destination(self, cargo_id, destination):
        self.bookingapplication.change_destination(cargo_id, destination)


@subclassevents
class Cargo(BaseAggregateRoot):

    @classmethod
    def new(cls, origin, destination, arrival_deadline):
        cargo = cls.__create__(
            origin=origin, destination=destination, arrival_deadline=arrival_deadline
        )
        cargo.__save__()
        return cargo

    def __init__(self, origin, destination, arrival_deadline, **kwargs):
        super().__init__(**kwargs)
        self.origin = origin
        self.destination = destination
        self.arrival_deadline = arrival_deadline

    def change_destination(self, destination):
        self.__trigger_event__(self.DestinationChanged, destination=destination)

    class DestinationChanged(DomainEvent):
        def mutate(self, obj):
            cargo = cast(obj, Cargo)
            cargo.destination = self.destination

        @property
        def destination(self):
            return self.__dict__['destination']


class CargoNotFound(Exception):
    pass


class BookingApplication(ProcessApplication):
    persist_event_type = Cargo.Event

    def book_new_cargo(self, origin, destination, arrival_deadline):
        return Cargo.new(origin, destination, arrival_deadline).id

    def get_cargo(self, cargo_id) -> Cargo:
        try:
            return self.repository[cargo_id]
        except RepositoryKeyError:
            raise CargoNotFound(cargo_id)

    def change_destination(self, cargo_id, destination):
        cargo = self.get_cargo(cargo_id)
        cargo.change_destination(destination)


class IncidentLoggingApplication(ProcessApplication):
    pass
