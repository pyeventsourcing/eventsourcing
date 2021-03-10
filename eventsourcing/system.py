from abc import ABC, abstractmethod
from collections import defaultdict
from threading import Event, Lock, Thread
from typing import Dict, Iterable, Iterator, List, Set, Tuple, Type, TypeVar

from eventsourcing.application import Application, NotificationLog, Section
from eventsourcing.domain import Aggregate, AggregateEvent
from eventsourcing.persistence import (
    Mapper,
    Notification,
    ProcessRecorder,
    Tracking,
)
from eventsourcing.utils import get_topic, resolve_topic


class ProcessEvent:
    """
    Keeps together a :class:`~eventsourcing.persistence.Tracking`
    object, which represents the position of a domain event notification
    in the notification log of a particular application, and the
    new domain events that result from processing that notification.
    """

    def __init__(self, tracking: Tracking):
        """
        Initalises the process event with the given tracking object.
        """
        self.tracking = tracking
        self.events: List[AggregateEvent] = []

    def save(self, *aggregates: Aggregate) -> None:
        """
        Collects pending domain events from the given aggregate.
        """
        for aggregate in aggregates:
            self.events += aggregate.collect_events()


class Follower(Application):
    """
    Extends the :class:`~eventsourcing.application.Application` class
    by using a process recorder as its application recorder, by keeping
    track of the applications it is following, and pulling and processing
    new domain event notifications through its :func:`policy` method.
    """

    def __init__(self) -> None:
        super().__init__()
        self.readers: Dict[
            str,
            Tuple[
                NotificationLogReader,
                Mapper[AggregateEvent],
            ],
        ] = {}
        self.recorder: ProcessRecorder

    def construct_recorder(self) -> ProcessRecorder:
        """
        Constructs and returns a :class:`~eventsourcing.persistence.ProcessRecorder`
        for the application to use as its application recorder.
        """
        return self.factory.process_recorder()

    def follow(self, name: str, log: NotificationLog) -> None:
        """
        Constructs a notification log reader and a mapper for
        the named application, and adds them to its collection
        of readers.
        """
        assert isinstance(self.recorder, ProcessRecorder)
        reader = NotificationLogReader(log)
        mapper = self.construct_mapper(name)
        self.readers[name] = (reader, mapper)

    def pull_and_process(self, name: str) -> None:
        """
        Pulls and processes unseen domain event notifications
        from the notification log reader of the names application.

        Converts received event notifications to domain
        event objects, and then calls the :func:`policy`
        with a new :class:`ProcessEvent` object which
        contains a :class:`~eventsourcing.persistence.Tracking`
        object that keeps track of the name of the application
        and the position in its notification log from which the
        domain event notification was pulled. The policy will
        save aggregates to the process event object, using its
        :func:`~ProcessEvent.save` method, which collects pending
        domain events using the aggregates'
        :func:`~eventsourcing.domain.Aggregate.collect_events`
        method, and the process event object will then be recorded
        by calling the :func:`record` method.
        """
        reader, mapper = self.readers[name]
        start = self.recorder.max_tracking_id(name) + 1
        for notification in reader.read(start=start):
            domain_event = mapper.to_domain_event(notification)
            process_event = ProcessEvent(
                Tracking(
                    application_name=name,
                    notification_id=notification.id,
                )
            )
            self.policy(
                domain_event,
                process_event,
            )
            self.record(process_event)

    @abstractmethod
    def policy(
        self,
        domain_event: AggregateEvent,
        process_event: ProcessEvent,
    ) -> None:
        """
        Abstract domain event processing policy method. Must be
        implemented by event processing applications. When
        processing the given domain event, event processing
        applications must use the :func:`~ProcessEvent.save`
        method of the given process event object (instead of
        the application's :func:`~eventsourcing.application.Application.save`
        method) to collect pending events from changed aggregates,
        so that the new domain events will be recorded atomically
        with tracking information about the position of the given
        domain event's notification.
        """

    def record(self, process_event: ProcessEvent) -> None:
        """
        Records given process event in the application's process recorder.
        """
        self.events.put(
            **process_event.__dict__,
        )
        self.notify(process_event.events)


class Promptable(ABC):
    """
    Abstract base class for "promptable" objects.
    """

    @abstractmethod
    def receive_prompt(self, leader_name: str) -> None:
        """
        Receives the name of leader that has new domain
        event notifications.
        """


class Leader(Application):
    """
    Extends the :class:`~eventsourcing.application.Application`
    class by also being responsible for keeping track of
    followers, and prompting followers when there are new
    domain event notifications to be pulled and processed.
    """

    def __init__(self) -> None:
        super().__init__()
        self.followers: List[Promptable] = []

    def lead(self, follower: Promptable) -> None:
        """
        Adds given follower to a list of followers.
        """
        self.followers.append(follower)

    def notify(self, new_events: List[AggregateEvent]) -> None:
        """
        Extends the application :func:`~eventsourcing.application.Application.notify`
        method by calling :func:`prompt_followers` whenever new events have just
        been saved.
        """
        super().notify(new_events)
        if len(new_events):
            self.prompt_followers()

    def prompt_followers(self) -> None:
        """
        Prompts followers by calling their :func:`~Promptable.receive_prompt`
        methods with the name of the application.
        """
        name = self.__class__.__name__
        for follower in self.followers:
            follower.receive_prompt(name)


class ProcessApplication(Leader, Follower, ABC):
    """
    Base class for event processing applications
    that are both "leaders" and followers".
    """


class System:
    """
    Defines a system of applications.
    """

    def __init__(
        self,
        pipes: Iterable[Iterable[Type[Application]]],
    ):
        nodes: Dict[str, Type[Application]] = {}
        edges: Set[Tuple[str, str]] = set()
        # Build nodes and edges.
        for pipe in pipes:
            follower_cls = None
            for cls in pipe:
                nodes[cls.__name__] = cls
                if follower_cls is None:
                    follower_cls = cls
                else:
                    leader_cls = follower_cls
                    follower_cls = cls
                    edges.add(
                        (
                            leader_cls.__name__,
                            follower_cls.__name__,
                        )
                    )

        self.edges = list(edges)
        self.nodes: Dict[str, str] = {}
        for name in nodes:
            topic = get_topic(nodes[name])
            self.nodes[name] = topic
        # Identify leaders and followers.
        self.follows: Dict[str, List[str]] = defaultdict(list)
        self.leads: Dict[str, List[str]] = defaultdict(list)
        for edge in edges:
            self.leads[edge[0]].append(edge[1])
            self.follows[edge[1]].append(edge[0])

        # Check followers are followers.
        for name in self.follows:
            if not issubclass(nodes[name], Follower):
                raise TypeError("Not a follower class: %s" % nodes[name])

        # Check each process is a process application class.
        for name in self.processors:
            if not issubclass(nodes[name], ProcessApplication):
                raise TypeError("Not a process application class: %s" % nodes[name])

    @property
    def leaders(self) -> Iterable[str]:
        return self.leads.keys()

    @property
    def leaders_only(self) -> Iterable[str]:
        for name in self.leads.keys():
            if name not in self.follows:
                yield name

    @property
    def followers(self) -> Iterable[str]:
        return self.follows.keys()

    @property
    def processors(self) -> Iterable[str]:
        return set(self.leaders).intersection(self.followers)

    def get_app_cls(self, name: str) -> Type[Application]:
        cls = resolve_topic(self.nodes[name])
        assert issubclass(cls, Application)
        return cls

    def leader_cls(self, name: str) -> Type[Leader]:
        cls = self.get_app_cls(name)
        if issubclass(cls, Leader):
            return cls
        else:
            cls = type(
                cls.__name__,
                (Leader, cls),
                {},
            )
            assert issubclass(cls, Leader)
            return cls

    def follower_cls(self, name: str) -> Type[Follower]:
        cls = self.get_app_cls(name)
        assert issubclass(cls, Follower)
        return cls


A = TypeVar("A")


class Runner(ABC):
    """
    Abstract base class for system runners.
    """

    def __init__(self, system: System):
        self.system = system
        self.is_started = False

    @abstractmethod
    def start(self) -> None:
        """
        Starts the runner.
        """
        if self.is_started:
            raise RunnerAlreadyStarted()
        self.is_started = True

    @abstractmethod
    def stop(self) -> None:
        """
        Stops the runner.
        """

    @abstractmethod
    def get(self, cls: Type[A]) -> A:
        """
        Returns an application instance for given application class.
        """


class RunnerAlreadyStarted(Exception):
    """
    Raised when runner is already started.
    """


class SingleThreadedRunner(Runner, Promptable):
    """
    Runs a :class:`System` in a single thread.
    A single threaded runner is a runner, and so implements the
    :func:`start`, :func:`stop`, and :func:`get` methods.
    A single threaded runner is also a :class:`Promptable` object, and
    implements the :func:`receive_prompt` method by collecting prompted
    names.
    """

    def __init__(self, system: System):
        """
        Initialises runner with the given :class:`System`.
        """
        super().__init__(system)
        self.apps: Dict[str, Application] = {}
        self.prompts_received: List[str] = []
        self.is_prompting = False

    def start(self) -> None:
        """
        Starts the runner.
        The applications are constructed, and setup to lead and follow
        each other, according to the system definition.
        The followers are setup to follow the applications they follow
        (have a notification log reader with the notification log of the
        leader), and their leaders are setup to lead the runner itself
        (send prompts).
        """

        super().start()

        # Construct followers.
        for name in self.system.followers:
            self.apps[name] = self.system.follower_cls(name)()

        # Construct leaders.
        for name in self.system.leaders_only:
            self.apps[name] = self.system.leader_cls(name)()

        # Lead and follow.
        for edge in self.system.edges:
            leader = self.apps[edge[0]]
            follower = self.apps[edge[1]]
            assert isinstance(leader, Leader)
            assert isinstance(follower, Follower)
            leader.lead(self)
            follower.follow(leader.__class__.__name__, leader.log)

    def receive_prompt(self, leader_name: str) -> None:
        """
        Receives prompt by appending name of
        leader to list of prompted names.
        Unless this method has previously been called but not
        yet returned, it will then proceed to forward the prompts
        received to its application by calling the application's
        :func:`~Follower.pull_and_process` method for each prompted name.
        """
        if leader_name not in self.prompts_received:
            self.prompts_received.append(leader_name)
        if not self.is_prompting:
            self.is_prompting = True
            while self.prompts_received:
                prompt = self.prompts_received.pop(0)
                for name in self.system.leads[prompt]:
                    follower = self.apps[name]
                    assert isinstance(follower, Follower)
                    follower.pull_and_process(prompt)
            self.is_prompting = False

    def stop(self) -> None:
        self.apps.clear()

    def get(self, cls: Type[A]) -> A:
        app = self.apps[cls.__name__]
        assert isinstance(app, cls)
        return app


class MultiThreadedRunner(Runner):
    """
    Runs a :class:`System` with a :class:`MultiThreadedRunnerThread` for each
    follower in the system definition.
    It is a runner, and so implements the :func:`start`, :func:`stop`,
    and :func:`get` methods.
    """

    def __init__(self, system: System):
        """
        Initialises runner with the given :class:`System`.
        """
        super().__init__(system)
        self.apps: Dict[str, Application] = {}
        self.threads: Dict[str, MultiThreadedRunnerThread] = {}
        self.is_stopping = Event()

    def start(self) -> None:
        """
        Starts the runner.

        A multi-threaded runner thread is started for each
        'follower' application in the system, and constructs
        an instance of each non-follower leader application in
        the system. The followers are then setup to follow the
        applications they follow (have a notification log reader
        with the notification log of the leader), and their leaders
        are  setup to lead the follower's thead (send prompts).
        """
        super().start()

        # Construct followers.
        for name in self.system.followers:
            app_class = self.system.follower_cls(name)
            thread = MultiThreadedRunnerThread(
                app_class=app_class,
                is_stopping=self.is_stopping,
            )
            self.threads[name] = thread
            thread.start()
            if (not thread.is_running.wait(timeout=5)) or thread.has_stopped.is_set():
                self.stop()
                raise Exception(f"Thread for '{app_class.__name__}' failed to start")
            self.apps[name] = thread.app

        # Construct non-follower leaders.
        for name in self.system.leaders_only:
            app = self.system.leader_cls(name)()
            self.apps[name] = app

        # Lead and follow.
        for edge in self.system.edges:
            leader = self.apps[edge[0]]
            follower = self.apps[edge[1]]
            assert isinstance(leader, Leader)
            assert isinstance(follower, Follower)
            follower.follow(leader.__class__.__name__, leader.log)
            thread = self.threads[edge[1]]
            leader.lead(thread)

    def stop(self) -> None:
        self.is_stopping.set()
        for thread in self.threads.values():
            thread.is_prompted.set()
            thread.join()

    @property
    def has_stopped(self) -> bool:
        return all([t.has_stopped.is_set() for t in self.threads.values()])

    def get(self, cls: Type[A]) -> A:
        app = self.apps[cls.__name__]
        assert isinstance(app, cls)
        return app


class MultiThreadedRunnerThread(Promptable, Thread):
    """
    Runs one process application for a
    :class:`~eventsourcing.system.MultiThreadedRunner`.

    A multi-threaded runner thread is a :class:`~eventsourcing.system.Promptable`
    object, and implements the :func:`receive_prompt` method by collecting
    prompted names and setting its threading event 'is_prompted'.

    A multi-threaded runner thread is a Python :class:`threading.Thread` object,
    and implements the thread's :func:`run` method by waiting until the
    'is_prompted' event has been set and then calling its process application's
    :func:`~eventsourcing.system.Follower.pull_and_process`
    method once for each prompted name. It is expected that
    the process application will have been set up by the runner
    with a notification log reader from which event notifications
    will be pulled.
    """

    def __init__(
        self,
        app_class: Type[Follower],
        is_stopping: Event,
    ):
        super().__init__()
        self.app_class = app_class
        self.is_stopping = is_stopping
        self.has_stopped = Event()
        self.has_errored = Event()
        self.is_prompted = Event()
        self.prompted_names: List[str] = []
        self.prompted_names_lock = Lock()
        self.setDaemon(True)
        self.is_running = Event()

    def run(self) -> None:
        """
        Begins by constructing an application instance from
        given application class and then loops forever until
        stopped. The loop blocks on waiting for the 'is_prompted'
        event to be set, then forwards the prompts already received
        to its application by calling the application's
        :func:`~Follower.pull_and_process` method for each prompted name.
        """
        try:
            self.app: Follower = self.app_class()
        except Exception:
            self.has_errored.set()
            self.has_stopped.set()
            raise
        finally:
            self.is_running.set()  # pragma: no cover
            # -----------------------^ weird branch coverage thing with Python 3.9

        try:
            while True:
                self.is_prompted.wait()
                if self.is_stopping.is_set():
                    self.has_stopped.set()
                    break
                with self.prompted_names_lock:
                    prompted_names = self.prompted_names
                    self.prompted_names = []
                    self.is_prompted.clear()
                for name in prompted_names:
                    self.app.pull_and_process(name)
        except Exception:
            self.has_errored.set()
            self.has_stopped.set()
            self.is_stopping.is_set()
            raise

    def receive_prompt(self, leader_name: str) -> None:
        """
        Receives prompt by appending name of
        leader to list of prompted names.
        """
        with self.prompted_names_lock:
            if leader_name not in self.prompted_names:
                self.prompted_names.append(leader_name)
            self.is_prompted.set()


class NotificationLogReader:
    """
    Reads domain event notifications from a notification log.
    """

    DEFAULT_SECTION_SIZE = 10

    def __init__(
        self,
        notification_log: NotificationLog,
        section_size: int = DEFAULT_SECTION_SIZE,
    ):
        """
        Initialises a reader with the given notification log,
        and optionally a section size integer which determines
        the requested number of domain event notifications in
        each section retrieved from the notification log.
        """
        self.notification_log = notification_log
        self.section_size = section_size

    def read(self, *, start: int) -> Iterator[Notification]:
        """
        Returns a generator that yields event notifications
        from the reader's notification log, starting from
        given start position (a notification ID).

        This method traverses the linked list of sections presented by
        a notification log, and yields the individual event notifications
        that are contained in each section. When all the event notifications
        from a section have been yielded, the reader will retrieve the next
        section, and continue yielding event notification until all subsequent
        event notifications in the notification log from the start position
        have been yielded.
        """
        section_id = "{},{}".format(start, start + self.section_size - 1)
        while True:
            section: Section = self.notification_log[section_id]
            for item in section.items:
                # Todo: Reintroduce if supporting
                #  sections with regular alignment?
                # if item.id < start:
                #     continue
                yield item
            if section.next_id is None:
                break
            else:
                section_id = section.next_id
