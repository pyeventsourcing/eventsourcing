.. _Bank accounts example:

Bank accounts example
=====================

This example demonstrates an event-sourced application
object, and an event-sourced aggregate that uses the
declarative syntax.

Test case
---------

To keep things simple, we can define a test case using Python's
``unittest`` module.

.. code:: python

    import unittest

For the purpose of showing how the application object
might be used, the test runs through a scenario that
exercises all the methods of the application in one
test method.

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/test.py
    :pyobject: TestBankAccounts


Application
-----------

The ``BankAccounts`` application class has command and query methods for interacting
with the domain model.

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/application.py
    :pyobject: BankAccounts

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/application.py
    :pyobject: AccountNotFoundError

Domain model
------------

The ``BankAccount`` aggregate class is defined using the declarative syntax.

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/domainmodel.py
    :pyobject: BankAccount

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/domainmodel.py
    :pyobject: TransactionError

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/domainmodel.py
    :pyobject: AccountClosedError

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/domainmodel.py
    :pyobject: InsufficientFundsError


Run tests
---------

The test case will now pass.

.. code:: python

    if __name__ == '__main__':
        unittest.main()

::

    .
    ----------------------------------------------------------------------
    Ran 1 test in 0.005s

    OK
