==========
Background
==========

Although the event sourcing patterns are each quite simple, and they can
be reproduced in code for each project, they do suggest cohesive
mechanisms, for example applying and publishing the events generated
within domain entities, storing and retrieving selections of the events
in a highly scalable manner, replaying the stored events for a
particular entity to obtain the current state, and projecting views of
the event stream that are persisted in other models. Quoting from the
"Cohesive Mechanism" pages in Eric Evan's Domain Driven Design book:

.. pull-quote::

    **"Therefore: Partition a conceptually COHESIVE MECHANISM into a separate
    lightweight framework. Particularly watch for formalisms for
    well-documented categories of algorithms. Expose the capabilities of the
    framework with an INTENTION-REVEALING INTERFACE. Now the other elements
    of the domain can focus on expressing the problem ("what"), delegating
    the intricacies of the solution ("how") to the framework."**

Inspiration:

-  Martin Fowler's `article on event sourcing <http://martinfowler.com/eaaDev/EventSourcing.html>`__

-  Greg Young's `discussions about event sourcing <https://www.youtube.com/watch?v=JHGkaShoyNs>`__,
   and `EventStore system <https://geteventstore.com/>`__

-  Robert Smallshire's `brilliant example on Bitbucket <https://bitbucket.org/sixty-north/d5-kanban-python/src>`__

-  Various professional projects that called for this approach, for
   which I didn't want to rewrite the same things each time

See also:

-  `Evaluation of using NoSQL databases in an event sourcing system
   <http://www.diva-portal.se/smash/get/diva2:877307/FULLTEXT01.pdf>`__ by
   Johan Rothsberg

-  `Object-relational impedance mismatch
   <https://en.wikipedia.org/wiki/Object-relational\_impedance\_mismatch>`__
   page on Wikipedia

-  `An introduction to event storming
   <https://techbeacon.com/introduction-event-storming-easy-way-achieve-domain-driven-design>`__
   by a Steven Lowe, principal consultant developer at ThoughtWorks.

