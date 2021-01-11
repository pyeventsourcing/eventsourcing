===================
Systems and runners
===================


Overview
========

A design for distributed systems is introduced that uses event-sourced
applications as building blocks. The earlier design of the
:doc:`event-sourced application </topics/application>` is extended in
the design of the "process application". Process application classes
can be composed into a set of pipeline expressions that together define
a system pipeline. This definition of a system can be entirely independent
of infrastructure. Such a system can be run in different ways with identical
results.

Rather than seeking reliability in mathematics (e.g.
`CSP <https://en.wikipedia.org/wiki/Communicating_sequential_processes>`__)
or in physics (e.g. `Actor model <https://en.wikipedia.org/wiki/Actor_model>`__),
the approach taken here is to seek reliable foundations in engineering empiricism,
specifically in the empirical reliability of `counting <https://en.wikipedia.org/wiki/Counting>`__
and of `ACID database transactions <https://en.wikipedia.org/wiki/ACID_(computer_science)>`__.

Just as event sourcing "atomised" application state as a set of domain
events, similarly the processing of domain events can be atomised as a
potentially distributed set of local "process events" in which new domain
events may occur. The subjective aim of a process event is "catching up
on what happened".

The processing of domain events is designed to be atomic and successive
so that processing can progress in a determinate manner according to
infrastructure availability. A description of a design
pattern for process events is included at the end of this section.

...

Classes
=======

.. automodule:: eventsourcing.system
    :show-inheritance:
    :member-order: bysource
    :members:
    :special-members:
    :exclude-members: __weakref__, __dict__
