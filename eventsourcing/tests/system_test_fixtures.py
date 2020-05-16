import logging
import os
from uuid import NAMESPACE_OID, uuid5

from eventsourcing.application.process import ProcessApplication, WrappedRepository
from eventsourcing.domain.model.aggregate import BaseAggregateRoot
from eventsourcing.domain.model.decorators import retry
from eventsourcing.exceptions import OperationalError, RecordConflictError
from eventsourcing.tests.test_process import ExampleAggregate


def set_db_uri():
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    user = os.getenv("MYSQL_USER", "eventsourcing")
    password = os.getenv("MYSQL_PASSWORD", "eventsourcing")
    db_uri = (
        "mysql+pymysql://{}:{}@{}/eventsourcing?charset=utf8mb4&binary_prefix=true"
    ).format(user, password, host)
    os.environ["DB_URI"] = db_uri


class Order(BaseAggregateRoot):
    def __init__(self, **kwargs):
        super(Order, self).__init__(**kwargs)
        self.is_reserved = False
        self.is_paid = False

    class Event(BaseAggregateRoot.Event):
        pass

    class Created(Event, BaseAggregateRoot.Created):
        pass

    def set_is_reserved(self, reservation_id):
        self.__trigger_event__(Order.Reserved, reservation_id=reservation_id)

    class Reserved(Event):
        def mutate(self, order):
            assert not order.is_reserved, "Order {} already reserved.".format(order.id)
            order.is_reserved = True
            order.reservation_id = self.reservation_id

        @property
        def reservation_id(self):
            return self.__dict__["reservation_id"]

    def set_is_paid(self, payment_id):
        self.__trigger_event__(self.Paid, payment_id=payment_id)

    class Paid(Event):
        def mutate(self, order):
            assert not order.is_paid, "Order {} already paid.".format(order.id)
            order.is_paid = True
            order.payment_id = self.payment_id

        @property
        def payment_id(self):
            return self.__dict__["payment_id"]


class Reservation(BaseAggregateRoot):
    def __init__(self, order_id, **kwargs):
        super(Reservation, self).__init__(**kwargs)
        self.order_id = order_id

    class Event(BaseAggregateRoot.Event):
        pass

    class Created(Event, BaseAggregateRoot.Created):
        pass

    @classmethod
    def create(cls, order_id):
        return cls.__create__(
            originator_id=Reservation.create_reservation_id(order_id), order_id=order_id
        )

    @classmethod
    def create_reservation_id(cls, order_id):
        return uuid5(NAMESPACE_OID, str(order_id))


class Payment(BaseAggregateRoot):
    def __init__(self, order_id, **kwargs):
        super(Payment, self).__init__(**kwargs)
        self.order_id = order_id

    class Event(BaseAggregateRoot.Event):
        pass

    class Created(Event, BaseAggregateRoot.Created):
        pass

    @classmethod
    def make(self, order_id):
        return self.__create__(order_id=order_id)


@retry((OperationalError, RecordConflictError), max_attempts=10, wait=0.01)
def create_new_order():
    order = Order.__create__()
    order.__save__()
    return order.id


logger = logging.getLogger()


class Orders(ProcessApplication[Order, Order.Event]):
    persist_event_type = Order.Created
    # set_notification_ids = True
    # use_cache = True

    def policy(self, repository, event):
        if isinstance(event, Reservation.Created):
            # Set the order as reserved.
            order = self.get_order(order_id=event.order_id, repository=repository)
            assert not order.is_reserved
            order.set_is_reserved(event.originator_id)

        elif isinstance(event, Payment.Created):
            # Set the order as paid.
            order = repository[event.order_id]
            assert isinstance(order, Order)
            assert not order.is_paid
            order.set_is_paid(event.originator_id)

    @retry((OperationalError, RecordConflictError), max_attempts=10, wait=0.01)
    def create_new_order(self):
        order = Order.__create__()
        order.__save__()
        return order.id

    def is_order_reserved(self, order_id):
        order = self.get_order(order_id)
        return order is not None

    def is_order_paid(self, order_id):
        order = self.get_order(order_id)
        return order is not None and order.is_paid

    def get_order(self, order_id, repository: WrappedRepository = None):
        try:
            return (repository or self.repository)[order_id]
        except KeyError:
            return None


class Reservations(ProcessApplication[Reservation, Reservation.Event]):
    def policy(self, repository, event):
        if isinstance(event, Order.Created):
            # Create a reservation.
            return Reservation.create(order_id=event.originator_id)


class Payments(ProcessApplication):
    def policy(self, repository, event):
        if isinstance(event, Order.Reserved):
            # Make a payment.
            return Payment.make(order_id=event.originator_id)


class Examples(ProcessApplication[ExampleAggregate, ExampleAggregate.Event]):
    persist_event_type = ExampleAggregate.Created

    def policy(self, repository, event):
        if isinstance(event, ExampleAggregate.Created):
            example_aggregate = repository[event.originator_id]
            assert isinstance(example_aggregate, ExampleAggregate)
            example_aggregate.move_on()
