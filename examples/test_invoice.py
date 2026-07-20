from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa:TC003
from decimal import Decimal
from enum import Enum
from typing import Any
from unittest import TestCase

from eventsourcing.domain import triggers
from eventsourcing.pydantic.application import PydanticApplication
from eventsourcing.pydantic.mutable import PydanticAggregate


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


class Invoice(PydanticAggregate):
    @triggers("Initiated")
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

    @property
    def number(self) -> str:
        return self._number

    @number.setter
    @triggers("NumberUpdated")
    def number(self, value: str) -> None:
        assert self.status == Status.INITIATED
        self._number = value

    @property
    def amount(self) -> Decimal:
        return self._amount

    @amount.setter
    @triggers("AmountUpdated")
    def amount(self, value: Decimal) -> None:
        assert self.status == Status.INITIATED
        self._amount = value

    @triggers("Issued")
    def issue(self, issued_by: str, timestamp: datetime | Any = None) -> None:
        self.issued_by = issued_by
        self.issued_on = timestamp
        self.status = Status.ISSUED

    @triggers("Sent")
    def send(self, sent_via: SendMethod, timestamp: datetime | Any = None) -> None:
        self.sent_via = sent_via
        self.sent_at = timestamp
        self.status = Status.SENT


class InvoicingApplication(PydanticApplication):
    pass


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

        app = InvoicingApplication(env={"IS_SNAPSHOTTING_ENABLED": "y"})

        app.save(invoice)

        copy = app.repository.get(invoice.id, Invoice)
        self.assertEqual(invoice, copy)

        # assert app.snapshots is not None
        # snapshots = list(app.snapshots.get(invoice.id))
        # self.assertEqual(len(snapshots), 0)
        #
        # app.take_snapshot(invoice.id, Invoice)
        #
        # copy = app.repository.get(invoice.id, Invoice)
        # self.assertEqual(invoice, copy)
        #
        # copy = app.repository.get(invoice.id, Invoice, version=1)
        # self.assertNotEqual(invoice, copy)
        #
        # snapshots = list(app.snapshots.get(invoice.id))
        # self.assertEqual(len(snapshots), 1)
        #
        # snapshot = cast("Snapshot", snapshots[0])
        # copy2 = snapshot.mutate(object.__new__(Invoice))
        # self.assertEqual(invoice, copy2)
