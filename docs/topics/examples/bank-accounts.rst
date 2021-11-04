.. _Bank accounts example:

Bank accounts example
=====================

This example demonstrates a straightforward event-sourced
application, which has an event-sourced aggregate that uses
the :ref:`declarative syntax <Declarative syntax>`.

Test case
---------

A test case is defined using the ``unittest`` module
in the Python Standard Library.

.. code:: python

    import unittest

For the purpose of showing how the application object
might be used, the test runs through a scenario that
exercises all the methods of the application in one
test method.

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/test.py
    :pyobject: TestBankAccounts


Domain model
------------

The ``BankAccount`` aggregate class is defined using the
:ref:`declarative syntax <Declarative syntax>`.

The ``BankAccount`` aggregate has a balance and an overdraft limit. Accounts
can be opened and closed. Accounts can be credited and debited, which affects
the balance. Neither credits nor debits are not allowed if the account has been
closed. Debits are not allowed if the balance would go below the overdraft limit.
The overdraft limit can be adjusted.

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/domainmodel.py
    :pyobject: BankAccount

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/domainmodel.py
    :pyobject: TransactionError

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/domainmodel.py
    :pyobject: AccountClosedError

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/domainmodel.py
    :pyobject: InsufficientFundsError


Application
-----------

The ``BankAccounts`` application has command and query methods for interacting
with the domain model.

The ``BankAccounts`` application allows new accounts to be opened. Existing accounts
can be closed. Deposits and withdraws can be made on open accounts. Transfers can
be made between open accounts, if there are sufficient funds on the debited account.
All actions are atomic, including transfers between accounts.

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/application.py
    :pyobject: BankAccounts

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/application.py
    :pyobject: AccountNotFoundError


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
