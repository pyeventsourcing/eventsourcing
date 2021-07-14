from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from unittest import TestCase

from eventsourcing.application import Application
from eventsourcing.domain import Aggregate, event
from eventsourcing.persistence import Transcoding


class Status(Enum):
    INITIATED = 1
    ISSUED = 2
    SENT = 3


class SendMethod(Enum):
    EMAIL = 1
    POST = 2


@dataclass
class Person:
    name: str
    address: str


class Invoice(Aggregate):
    @event("Initiated")
    def __init__(self, number: str, amount: Decimal, issued_to: Person):
        self.number = number
        self.amount = amount
        self.issued_to = issued_to
        self.initiated_at = self.modified_on
        self.status = Status.INITIATED

    @event("Issued")
    def issue(self, issued_by: str):
        self.issued_by = issued_by
        self.issued_at = self.modified_on
        self.status = Status.ISSUED

    @event("Sent")
    def send(self, sent_via: SendMethod):
        self.sent_via = sent_via
        self.sent_at = self.modified_on
        self.status = Status.SENT


class PersonAsDict(Transcoding):
    name = "person_as_dict"
    type = Person

    def encode(self, obj: Person) -> dict:
        return obj.__dict__

    def decode(self, data: dict) -> Person:
        return Person(**data)


class SendMethodAsStr(Transcoding):
    name = "send_method_str"
    type = SendMethod

    def encode(self, obj: SendMethod) -> str:
        return obj.name

    def decode(self, data: str) -> SendMethod:
        return getattr(SendMethod, data)


class StatusAsStr(Transcoding):
    name = "status_str"
    type = Status

    def encode(self, obj: Status) -> str:
        return obj.name

    def decode(self, data: str) -> Status:
        return getattr(Status, data)


class TestInvoice(TestCase):
    def test(self):
        invoice = Invoice(
            number="INV/2021/11/01",
            amount=Decimal("34.20"),
            issued_to=Person("Oscar the Grouch", "123 Sesame Street"),
        )
        self.assertEqual(invoice.number, "INV/2021/11/01")
        self.assertEqual(invoice.amount, Decimal("34.20"))
        self.assertEqual(
            invoice.issued_to, Person("Oscar the Grouch", "123 Sesame Street")
        )
        self.assertEqual(invoice.status, Status.INITIATED)

        invoice.issue(issued_by="Cookie Monster")
        self.assertEqual(invoice.issued_by, "Cookie Monster")
        self.assertEqual(invoice.status, Status.ISSUED)

        invoice.send(sent_via=SendMethod.EMAIL)
        self.assertEqual(invoice.sent_via, SendMethod.EMAIL)
        self.assertEqual(invoice.status, Status.SENT)

        app = Application(env={"IS_SNAPSHOTTING_ENABLED": "y"})
        app.mapper.transcoder.register(PersonAsDict())
        app.mapper.transcoder.register(SendMethodAsStr())
        app.mapper.transcoder.register(StatusAsStr())

        app.save(invoice)

        copy = app.repository.get(invoice.id)
        self.assertEqual(invoice, copy)

        snapshots = list(app.snapshots.get(invoice.id))
        self.assertEqual(len(snapshots), 0)

        app.take_snapshot(invoice.id)

        copy = app.repository.get(invoice.id)
        self.assertEqual(invoice, copy)

        copy = app.repository.get(invoice.id, version=1)
        self.assertNotEqual(invoice, copy)

        snapshots = list(app.snapshots.get(invoice.id))
        self.assertEqual(len(snapshots), 1)

        snapshot = snapshots[0]
        copy = snapshot.mutate()
        self.assertEqual(invoice, copy)
