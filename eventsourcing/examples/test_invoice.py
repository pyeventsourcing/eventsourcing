from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, cast
from unittest import TestCase

from eventsourcing.application import Application
from eventsourcing.domain import Aggregate, Snapshot, event
from eventsourcing.persistence import Transcoding

if TYPE_CHECKING:  # pragma: nocover
    from datetime import datetime


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
    def __init__(
        self,
        number: str,
        amount: Decimal,
        issued_to: Person,
        timestamp: datetime | Any = None,
    ):
        self._number = number
        self._amount = amount
        self.issued_to = issued_to
        self.initiated_at = timestamp
        self.status = Status.INITIATED

    def _get_number(self) -> str:
        return self._number

    @event
    def _number_updated(self, value: str) -> None:
        assert self.status == Status.INITIATED
        self._number = value

    number = property(_get_number, _number_updated)

    def _get_amount(self) -> Decimal:
        return self._amount

    @event("AmountUpdated")
    def _set_amount(self, value: Decimal) -> None:
        assert self.status == Status.INITIATED
        self._amount = value

    amount = property(_get_amount, _set_amount)

    @event("Issued")
    def issue(self, issued_by: str, timestamp: datetime | Any = None) -> None:
        self.issued_by = issued_by
        self.issued_on = timestamp
        self.status = Status.ISSUED

    @event("Sent")
    def send(self, sent_via: SendMethod, timestamp: datetime | Any = None) -> None:
        self.sent_via = sent_via
        self.sent_at = timestamp
        self.status = Status.SENT


class PersonAsDict(Transcoding):
    name = "person_as_dict"
    type = Person

    def encode(self, obj: Person) -> Dict[str, Any]:
        return obj.__dict__

    def decode(self, data: Dict[str, Any]) -> Person:
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
    def test(self) -> None:
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

        invoice.number = "INV/2021/11/02"
        self.assertEqual(invoice.number, "INV/2021/11/02")

        invoice.amount = Decimal("43.20")
        self.assertEqual(invoice.number, "INV/2021/11/02")

        invoice.issue(issued_by="Cookie Monster")
        self.assertEqual(invoice.issued_by, "Cookie Monster")
        self.assertEqual(invoice.status, Status.ISSUED)

        with self.assertRaises(AssertionError):
            invoice.number = "INV/2021/11/03"

        with self.assertRaises(AssertionError):
            invoice.amount = Decimal("54.20")

        invoice.send(sent_via=SendMethod.EMAIL)
        self.assertEqual(invoice.sent_via, SendMethod.EMAIL)
        self.assertEqual(invoice.status, Status.SENT)

        app: Application = Application(env={"IS_SNAPSHOTTING_ENABLED": "y"})
        app.mapper.transcoder.register(PersonAsDict())
        app.mapper.transcoder.register(SendMethodAsStr())
        app.mapper.transcoder.register(StatusAsStr())

        app.save(invoice)

        copy: Invoice = app.repository.get(invoice.id)
        self.assertEqual(invoice, copy)

        assert app.snapshots is not None
        snapshots = list(app.snapshots.get(invoice.id))
        self.assertEqual(len(snapshots), 0)

        app.take_snapshot(invoice.id)

        copy = app.repository.get(invoice.id)
        self.assertEqual(invoice, copy)

        copy = app.repository.get(invoice.id, version=1)
        self.assertNotEqual(invoice, copy)

        snapshots = list(app.snapshots.get(invoice.id))
        self.assertEqual(len(snapshots), 1)

        snapshot = cast(Snapshot, snapshots[0])
        copy2 = cast(Invoice, snapshot.mutate(None))
        self.assertEqual(invoice, copy2)
