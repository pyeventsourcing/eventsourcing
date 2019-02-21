import logging
import os

from eventsourcing.application.process import ProcessApplication
from eventsourcing.domain.model.aggregate import BaseAggregateRoot
from eventsourcing.domain.model.decorators import retry
from eventsourcing.exceptions import OperationalError, RecordConflictError
from eventsourcing.tests.test_process import ExampleAggregate


# Moved this stuff here to avoid "__main__ has no
# Reservation.Created" etc topic resolution errors.

def set_db_uri():
    host = os.getenv('MYSQL_HOST', '127.0.0.1')
    user = os.getenv('MYSQL_USER', 'root')
    password = os.getenv('MYSQL_PASSWORD', '')
    db_uri = 'mysql+pymysql://{}:{}@{}/eventsourcing?charset=utf8mb4&binary_prefix=true'.format(user, password, host)
    # raise Exception(db_uri)
    os.environ['DB_URI'] = db_uri


class Order(BaseAggregateRoot):
    def __init__(self, **kwargs):
        super(Order, self).__init__(**kwargs)
        self.is_reserved = False
        self.is_paid = False

    class Event(BaseAggregateRoot.Event): pass

    class Created(Event, BaseAggregateRoot.Created): pass

    class Reserved(Event):
        def mutate(self, order):
            assert not order.is_reserved, "Order {} already reserved.".format(order.id)
            order.is_reserved = True
            order.reservation_id = self.reservation_id

    class Paid(Event):
        def mutate(self, order):
            assert not order.is_paid, "Order {} already paid.".format(order.id)
            order.is_paid = True
            order.payment_id = self.payment_id

    def set_is_reserved(self, reservation_id):
        self.__trigger_event__(Order.Reserved, reservation_id=reservation_id)

    def set_is_paid(self, payment_id):
        self.__trigger_event__(self.Paid, payment_id=payment_id)


class Reservation(BaseAggregateRoot):
    def __init__(self, order_id, **kwargs):
        super(Reservation, self).__init__(**kwargs)
        self.order_id = order_id

    class Event(BaseAggregateRoot.Event): pass

    class Created(Event, BaseAggregateRoot.Created): pass

    @classmethod
    def create(cls, order_id):
        return cls.__create__(order_id=order_id)


class Payment(BaseAggregateRoot):
    def __init__(self, order_id, **kwargs):
        super(Payment, self).__init__(**kwargs)
        self.order_id = order_id

    class Event(BaseAggregateRoot.Event): pass

    class Created(Event, BaseAggregateRoot.Created): pass

    @classmethod
    def make(self, order_id):
        return self.__create__(order_id=order_id)


@retry((OperationalError, RecordConflictError), max_attempts=10, wait=0.01)
def create_new_order():
    order = Order.__create__()
    order.__save__()
    return order.id


logger = logging.getLogger()


class Orders(ProcessApplication):
    persist_event_type = Order.Created

    @staticmethod
    def policy(repository, event):
        if isinstance(event, Reservation.Created):
            # Set the order as reserved.
            order = repository[event.order_id]
            assert not order.is_reserved
            order.set_is_reserved(event.originator_id)
            # logger.info('set Order as reserved')
            # print(f'set Order {event.order_id} as reserved')

        elif isinstance(event, Payment.Created):
            # Set the order as paid.
            order = repository[event.order_id]
            assert not order.is_paid
            order.set_is_paid(event.originator_id)
            # logger.info('set Order as paid')
            # print(f'set Order {event.order_id} as paid')


class Reservations(ProcessApplication):
    @staticmethod
    def policy(repository, event):
        if isinstance(event, Order.Created):
            # Create a reservation.
            # time.sleep(0.5)
            # logger.info('created Reservation for order')
            # print(f'created Reservation for order {event.originator_id}')
            return Reservation.create(order_id=event.originator_id)


class Payments(ProcessApplication):
    @staticmethod
    def policy(repository, event):
        if isinstance(event, Order.Reserved):
            # Make a payment.
            # time.sleep(0.5)
            # logger.info('created Payment for order')
            # print(f'created Payment for order {event.originator_id}')
            return Payment.make(order_id=event.originator_id)


class Examples(ProcessApplication):
    persist_event_type = ExampleAggregate.Created

    @staticmethod
    def policy(repository, event):
        if isinstance(event, ExampleAggregate.Created):
            repository[event.originator_id].move_on()
