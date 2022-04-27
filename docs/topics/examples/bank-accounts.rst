.. _Bank accounts example:

Application 1 - Bank accounts
=============================

This example demonstrates a straightforward `event-sourced application <../application.html>`_.

Application
-----------

The ``BankAccounts`` application has command and query methods for interacting
with the domain model. New accounts can be opened. Existing accounts can be
closed. Deposits and withdraws can be made on open accounts. Transfers can be
made between open accounts, if there are sufficient funds on the debited account.
All actions are atomic, including transfers between accounts.

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/application.py


Domain model
------------

The ``BankAccount`` aggregate class is defined using the
:ref:`declarative syntax <Declarative syntax>`. It has a
balance and an overdraft limit. Accounts can be opened and
closed. Accounts can be credited and debited, which affects
the balance. Neither credits nor debits are allowed if
the account has been closed. Debits are not allowed if the
balance would go below the overdraft limit. The overdraft
limit can be adjusted.

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/domainmodel.py


Test case
---------

For the purpose of showing how the application object
might be used, the test runs through a scenario that
exercises all the methods of the application in one
test method.

.. literalinclude:: ../../../eventsourcing/examples/bankaccounts/test.py
