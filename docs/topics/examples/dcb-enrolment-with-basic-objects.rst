.. _DCB example 2:

DCB 2 - Basic DCB Objects
=========================

Here we meet the :doc:`course subscriptions challenge </topics/examples/dcb-enrolment-introduction>`
directly with DCB.

Application
-----------

The :class:`~examples.dcb_enrolment_with_basic_objects.application.EnrolmentWithBasicDcbObjects` application implements
:ref:`the enrolment interface <Enrolment interface>` introduced on the previous page, using the
basic :ref:`DCB objects <DCB Objects>` included in this library, and the :ref:`DCB application <DCB application>`
class.

Whilst the code is relatively verbose, the DCB approach can be understood directly
without any extra abstractions.

.. literalinclude:: ../../../examples/dcb_enrolment_with_basic_objects/application.py
    :pyobject: EnrolmentWithBasicDcbObjects


Test case
---------

The :ref:`enrolment test case <Enrolment test case>` is extended for
:class:`~examples.dcb_enrolment_with_basic_objects.application.EnrolmentWithBasicDcbObjects`.

.. literalinclude:: ../../../examples/dcb_enrolment_with_basic_objects/test_application.py
    :pyobject: TestEnrolmentWithBasicDcbObjects


