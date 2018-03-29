import os
import time
from unittest import TestCase, skipIf
from uuid import uuid4

import six

from eventsourcing.application.multiprocess import Multiprocess
from eventsourcing.application.process import Process, System
from eventsourcing.domain.model.aggregate import AggregateRoot
from eventsourcing.domain.model.decorators import retry
from eventsourcing.exceptions import OperationalError, RecordConflictError


class TestSystem(TestCase):

    def test_single_threaded_system(self):
        system = System(
            (Orders, Reservations, Orders, Payments, Orders),
        )

        with system:
            # Create new Order aggregate.
            order_id = create_new_order()

            # Check the order is reserved and paid.
            repository = system.orders.repository
            assert repository[order_id].is_reserved
            assert repository[order_id].is_paid

    def test_multi_process_system(self):

        os.environ['DB_URI'] = 'mysql+pymysql://root:@127.0.0.1/eventsourcing'

        with Orders(setup_tables=True) as app:
            # Create a new order.
            order_id = create_new_order()

            # Check new order exists in the repository.
            assert order_id in app.repository

        system = System(
            (Orders, Reservations, Orders, Payments, Orders),
        )

        multiprocess = Multiprocess(system)

        # Start multiprocessing system.
        with multiprocess:

            with Orders() as app:

                retries = 50
                while not app.repository[order_id].is_reserved:
                    time.sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_reserved"

                while retries and not app.repository[order_id].is_paid:
                    time.sleep(0.1)
                    retries -= 1
                    assert retries, "Failed set order.is_paid"

    def test_multi_pipeline(self):
        from eventsourcing.utils.uuids import uuid_from_pipeline_name

        os.environ['DB_URI'] = 'mysql+pymysql://root:@127.0.0.1/eventsourcing'

        # Set up the database.
        with Orders(setup_tables=True):
            pass

        system = System(
            (Orders, Reservations, Orders, Payments, Orders),
        )

        num_pipelines = 5

        pipeline_ids = [uuid_from_pipeline_name(i) for i in range(num_pipelines)]

        multiprocess = Multiprocess(system, pipeline_ids=pipeline_ids)

        num_orders_per_pipeline = 25

        # Start multiprocessing system.
        with multiprocess:

            order_ids = []

            with Orders(pipeline_id=pipeline_ids[0]) as app:
                # Create some new orders.
                for _ in range(num_orders_per_pipeline):

                    for pipeline_id in pipeline_ids:

                        app.event_store.record_manager.pipeline_id = pipeline_id

                        order_id = create_new_order()
                        order_ids.append(order_id)

                        multiprocess.prompt_about('orders', pipeline_id)

                        time.sleep(0.03)

                # Wait for orders to be reserved and paid.
                retries = 10 + 10 * num_orders_per_pipeline * len(pipeline_ids)
                for i, order_id in enumerate(order_ids):

                    while not app.repository[order_id].is_reserved:
                        time.sleep(0.1)
                        retries -= 1
                        assert retries, "Failed set order.is_reserved {} ({})".format(order_id, i)

                    while retries and not app.repository[order_id].is_paid:
                        time.sleep(0.1)
                        retries -= 1
                        assert retries, "Failed set order.is_paid ({})".format(i)

                # Calculate timings from event timestamps.
                orders = [app.repository[oid] for oid in order_ids]
                first_timestamp = min([o.__created_on__ for o in orders])
                last_timestamp = max([o.__last_modified__ for o in orders])
                duration = last_timestamp - first_timestamp
                rate = len(order_ids) / float(duration)
                period = 1 / rate
                print("Orders system processed {} orders in {:.3f}s at rate of {:.1f} "
                      "orders/s, {:.3f}s each".format(len(order_ids), duration, rate, period))

                # Print min, average, max duration.
                durations = [o.__last_modified__ - o.__created_on__ for o in orders]
                print("Min order processing time: {:.3f}s".format(min(durations)))
                print("Mean order processing time: {:.3f}s".format(sum(durations) / len(durations)))
                print("Max order processing time: {:.3f}s".format(max(durations)))

    def test_payments_policy(self):
        # Prepare fake repository with a real Order aggregate.
        order = Order.__create__()
        fake_repository = {order.id: order}

        # Check policy makes payment whenever order is reserved.
        event = Order.Reserved(originator_id=order.id, originator_version=1)

        with Payments() as process:
            payment = process.policy(repository=fake_repository, event=event)
            assert isinstance(payment, Payment), payment
            assert payment.order_id == order.id

    def test_orders_policy(self):
        # Prepare fake repository with a real Order aggregate.
        order = Order.__create__()
        fake_repository = {order.id: order}

        # Check order is not reserved.
        assert not order.is_reserved

        # Check order is set as reserved when reservation is created for the order.
        with Orders() as process:
            event = Reservation.Created(originator_id=uuid4(), originator_topic='', order_id=order.id)
            process.policy(repository=fake_repository, event=event)

        # Check order is reserved.
        assert order.is_reserved

    def tearDown(self):
        try:
            del (os.environ['DB_URI'])
        except KeyError:
            pass


# Second example - orders, reservations, payments.

class Order(AggregateRoot):
    def __init__(self, **kwargs):
        super(Order, self).__init__(**kwargs)
        self.is_reserved = False
        self.is_paid = False

    class Event(AggregateRoot.Event): pass

    class Created(Event, AggregateRoot.Created): pass

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


class Reservation(AggregateRoot):
    def __init__(self, order_id, **kwargs):
        super(Reservation, self).__init__(**kwargs)
        self.order_id = order_id

    class Event(AggregateRoot.Event): pass

    class Created(Event, AggregateRoot.Created): pass

    @classmethod
    def create(cls, order_id):
        return cls.__create__(order_id=order_id)


class Payment(AggregateRoot):
    def __init__(self, order_id, **kwargs):
        super(Payment, self).__init__(**kwargs)
        self.order_id = order_id

    class Event(AggregateRoot.Event): pass

    class Created(Event, AggregateRoot.Created): pass

    @classmethod
    def make(self, order_id):
        return self.__create__(order_id=order_id)


@retry((OperationalError, RecordConflictError), max_attempts=10, wait=0.01)
def create_new_order():
    order = Order.__create__()
    order.__save__()
    return order.id


class Orders(Process):
    persist_event_type = Order.Created

    def policy(self, repository, event):
        if isinstance(event, Reservation.Created):
            # Set the order as reserved.
            order = repository[event.order_id]
            assert not order.is_reserved
            order.set_is_reserved(event.originator_id)

        elif isinstance(event, Payment.Created):
            # Set the order as paid.
            order = repository[event.order_id]
            assert not order.is_paid
            order.set_is_paid(event.originator_id)


class Reservations(Process):
    def policy(self, repository, event):
        if isinstance(event, Order.Created):
            # Create a reservation.
            # sleep(0.5)
            return Reservation.create(order_id=event.originator_id)


class Payments(Process):
    def policy(self, repository, event):
        if isinstance(event, Order.Reserved):
            # Make a payment.
            # sleep(0.5)
            return Payment.make(order_id=event.originator_id)
