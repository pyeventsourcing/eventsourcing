========
Examples
========

This library contains a few example applications and systems.

*this page is under development --- please check back soon*


.. code:: python

    import unittest


Bank accounts
=============

Test first...

.. literalinclude:: ../../eventsourcing/examples/bankaccounts/test.py
    :pyobject: TestBankAccounts

The application class :class:`BankAccounts`...

.. literalinclude:: ../../eventsourcing/examples/bankaccounts/application.py
    :pyobject: BankAccounts

.. literalinclude:: ../../eventsourcing/examples/bankaccounts/application.py
    :pyobject: AccountNotFoundError

The aggregate class :class:`BankAccount`...

.. literalinclude:: ../../eventsourcing/examples/bankaccounts/domainmodel.py
    :pyobject: BankAccount

.. literalinclude:: ../../eventsourcing/examples/bankaccounts/domainmodel.py
    :pyobject: TransactionError

.. literalinclude:: ../../eventsourcing/examples/bankaccounts/domainmodel.py
    :pyobject: AccountClosedError

.. literalinclude:: ../../eventsourcing/examples/bankaccounts/domainmodel.py
    :pyobject: InsufficientFundsError

Run the test...

.. code:: python

    suite = unittest.TestSuite()
    suite.addTest(TestBankAccounts("test"))

    runner = unittest.TextTestRunner()
    result = runner.run(suite)

    assert result.wasSuccessful()


.. _Cargo shipping:

Cargo shipping
==============

Test first...

.. literalinclude:: ../../eventsourcing/examples/cargoshipping/test.py
    :pyobject: TestBookingService

Interface...

.. literalinclude:: ../../eventsourcing/examples/cargoshipping/interface.py
    :pyobject: BookingService

.. literalinclude:: ../../eventsourcing/examples/cargoshipping/interface.py
    :pyobject: select_preferred_itinerary


Application...

.. literalinclude:: ../../eventsourcing/examples/cargoshipping/application.py
    :pyobject: BookingApplication

.. literalinclude:: ../../eventsourcing/examples/cargoshipping/application.py
    :pyobject: HandlingActivityAsName

.. literalinclude:: ../../eventsourcing/examples/cargoshipping/application.py
    :pyobject: ItineraryAsDict

.. literalinclude:: ../../eventsourcing/examples/cargoshipping/application.py
    :pyobject: LegAsDict

.. literalinclude:: ../../eventsourcing/examples/cargoshipping/application.py
    :pyobject: LocationAsName



Domain model...

.. literalinclude:: ../../eventsourcing/examples/cargoshipping/domainmodel.py
    :pyobject: Cargo

.. literalinclude:: ../../eventsourcing/examples/cargoshipping/domainmodel.py
    :pyobject: HandlingActivity

.. literalinclude:: ../../eventsourcing/examples/cargoshipping/domainmodel.py
    :pyobject: Itinerary

.. literalinclude:: ../../eventsourcing/examples/cargoshipping/domainmodel.py
    :pyobject: Leg

.. literalinclude:: ../../eventsourcing/examples/cargoshipping/domainmodel.py
    :pyobject: Location



Run the test...

.. code:: python

    suite = unittest.TestSuite()
    suite.addTest(TestBookingService("test_admin_can_book_new_cargo"))
    suite.addTest(TestBookingService("test_scenario_cargo_from_hongkong_to_stockholm"))

    runner = unittest.TextTestRunner()
    result = runner.run(suite)

    assert result.wasSuccessful()

