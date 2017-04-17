Using with Web Frameworks
=========================

It's a good question. You can do it in the wsgi file. If you have test cases,
you can do it there too. Also if you have any workers (e.g. celery workers) you
can do it when they are initialised. I suggest having a factory method that
constructs and returns the application instance, and then calling that method
from the wsgi file, so you have an eventsourcing application object as a module
level variable, just like the wsgi application object.

The "rule" is that you only need one application instance per process.
Otherwise, there will be more than one attempt to store each event, which won't
work. I'm not going to use the word "singleton" because some get triggered by
it, but it's just like imported Python modules or Python strings: you need only
one instance per process.

The application object, in itself, is thread-safe because it is stateless. From
experience, the difficulty some have had is the publish-subscribe functions it
uses are at the level of the module, so that entity methods can publish events
without having any other dependencies. So if you wanted (for some reason, e.g.
in a test suite) to instantiate the application twice in the same process then
you simply need to close it first: to unsubscribe handlers and to close
database connections. Closing connections to services like databases and
message brokers is only polite, and can save resources. Unsubscribing before
resubscribing is essential to avoid trying to save each event more than once
(which will immediately cause concurrency exceptions to be raised).

The context manager aspect is only a convenient way of closing things at the
end. You can equally put the object in a try/finally block and call close().
The 'with' context manager Python syntax is just a nice way to say that.

Since you will need to use the eventsourcing application object in the view
methods, it's not good enough just to instantiate the application at the edge
of your system: the views also need to have the object. So you could somehow
pass the eventsourcing application object into the stack for each request, or
you could code your factory method so that it can be called many times and each
time will return the same object. If you do it like that, make sure that if the
application has been closed, the factory will create a new instance and not
just return a closed instance. You could call the factory function in each view
method that needs it, or you could make it a property of a base view class (if
you have one).

You could perhaps do it with some middleware, I didn't ever try doing it with
middleware.

Also, if your process forks after it loads the code, you will want to open the
application object in the child processes, after they have been forked. You
also need to avoid race conditions, so just doing it lazily from multi-threaded
requests often isn't good enough. Celery has a signal for it
(worker_process_init). There are various things in Django which provide similar
comfort. This can sometimes be a "tricky" area because sometimes Django
developers don't really have a very good understanding of the processes in
their services. Perhaps it would be better if the complexity was somehow
encapsulated, so it is hidden and "just works". I guess we've got some more
work to do with Django. I keep thinking it would be great to have something
that doesn't break the Django admin view, but that's a different (much bigger)
topic.
