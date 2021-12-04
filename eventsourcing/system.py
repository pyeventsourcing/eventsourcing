from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from queue import Queue
from threading import Event, Thread
from typing import (
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    cast,
)

from eventsourcing.application import (
    Application,
    NotificationLog,
    ProcessEvent,
    Section,
)
from eventsourcing.domain import Aggregate, AggregateEvent, TAggregate
from eventsourcing.persistence import (
    Mapper,
    Notification,
    ProcessRecorder,
    Tracking,
)
from eventsourcing.utils import EnvType, get_topic, resolve_topic


class Follower(Application[TAggregate]):
    """
    Extends the :class:`~eventsourcing.application.Application` class
    by using a process recorder as its application recorder, by keeping
    track of the applications it is following, and pulling and processing
    new domain event notifications through its :func:`policy` method.
    """

    follow_topics: Sequence[str] = []
    pull_section_size = 10

    def __init__(self, env: Optional[EnvType] = None) -> None:
        super().__init__(env)
        self.readers: Dict[
            str,
            Tuple[
                NotificationLogReader,
                Mapper,
            ],
        ] = {}
        self.recorder: ProcessRecorder
        self.is_threading_enabled = False

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
        reader = NotificationLogReader(log, section_size=self.pull_section_size)

        env = self.construct_env(name, self.env)
        factory = self.construct_factory(env)
        mapper = factory.mapper(self.construct_transcoder())
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
        start = self.recorder.max_tracking_id(name) + 1
        for domain_event, process_event in self.pull_events(name, start):
            self.process_event(domain_event, process_event)

    def pull_events(
        self, name: str, start: int
    ) -> Iterable[Tuple[AggregateEvent[TAggregate], ProcessEvent]]:
        reader, mapper = self.readers[name]
        for notification in reader.select(start=start, topics=self.follow_topics):
            domain_event = cast(
                AggregateEvent[TAggregate], mapper.to_domain_event(notification)
            )
            process_event = ProcessEvent(
                Tracking(
                    application_name=name,
                    notification_id=notification.id,
                )
            )
            yield domain_event, process_event

    def process_event(
        self, domain_event: AggregateEvent[TAggregate], process_event: ProcessEvent
    ) -> Optional[int]:
        self.policy(domain_event, process_event)
        returning = self.record(process_event)
        self.take_snapshots(process_event)
        self.notify(process_event.events)
        return returning

    @abstractmethod
    def policy(
        self,
        domain_event: AggregateEvent[TAggregate],
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


class Leader(Application[TAggregate]):
    """
    Extends the :class:`~eventsourcing.application.Application`
    class by also being responsible for keeping track of
    followers, and prompting followers when there are new
    domain event notifications to be pulled and processed.
    """

    def __init__(self, env: Optional[EnvType] = None) -> None:
        super().__init__(env)
        self.followers: List[Promptable] = []

    def lead(self, follower: Promptable) -> None:
        """
        Adds given follower to a list of followers.
        """
        self.followers.append(follower)

    def notify(self, new_events: List[AggregateEvent[Aggregate]]) -> None:
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


class ProcessApplication(Leader[TAggregate], Follower[TAggregate], ABC):
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
        pipes: Iterable[Iterable[Type[Application[Aggregate]]]],
    ):
        nodes: Dict[str, Type[Application[Aggregate]]] = {}
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

    def get_app_cls(self, name: str) -> Type[Application[Aggregate]]:
        cls = resolve_topic(self.nodes[name])
        assert issubclass(cls, Application)
        return cls

    def leader_cls(self, name: str) -> Type[Leader[Aggregate]]:
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

    def follower_cls(self, name: str) -> Type[Follower[Aggregate]]:
        cls = self.get_app_cls(name)
        assert issubclass(cls, Follower)
        return cls


A = TypeVar("A")


class Runner(ABC):
    """
    Abstract base class for system runners.
    """

    def __init__(self, system: System, env: Optional[EnvType] = None):
        self.system = system
        self.env = env
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


class PullingThreadError(Exception):
    """
    Raised when notification pulling thread fails.
    """


class ProcessingThreadError(Exception):
    """
    Raised when event processing thread fails.
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

    def __init__(self, system: System, env: Optional[EnvType] = None):
        """
        Initialises runner with the given :class:`System`.
        """
        super().__init__(system, env)
        self.apps: Dict[str, Application[Aggregate]] = {}
        self.prompts_received: List[str] = []
        self.is_prompting = False
        self.has_stopped = Event()

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
            self.apps[name] = self.system.follower_cls(name)(env=self.env)

        # Construct leaders.
        for name in self.system.leaders_only:
            leader = self.system.leader_cls(name)(env=self.env)
            self.apps[name] = leader

        # Subscribe to leaders.
        for name in self.system.leaders:
            leader = self.apps[name]
            leader.lead(self)

        # Setup followers to follow leaders.
        for edge in self.system.edges:
            leader = self.apps[edge[0]]
            follower = self.apps[edge[1]]
            assert isinstance(leader, Leader)
            assert isinstance(follower, Follower)
            follower.follow(edge[0], leader.log)

    def receive_prompt(self, leader_name: str) -> None:
        """
        Receives prompt by appending name of
        leader to list of prompted names.
        Unless this method has previously been called but not
        yet returned, it will then proceed to forward the prompts
        received to its application by calling the application's
        :func:`~Follower.pull_and_process` method for each prompted name.
        """
        # print(leader_name, "prompted followers..")
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

    def __init__(
        self,
        system: System,
        env: Optional[EnvType] = None,
        processing_queue_size: int = 100,
    ):
        """
        Initialises runner with the given :class:`System`.
        """
        super().__init__(system, env)
        self.processing_queue_size = processing_queue_size
        self.apps: Dict[str, Application[Aggregate]] = {}
        self.pulling_threads: Dict[str, Dict[str, PullingThread]] = {}
        self.processing_threads: Dict[str, ProcessingThread] = {}
        self.processing_queues: Dict[
            str, "Queue[List[Tuple[AggregateEvent[Aggregate], ProcessEvent]]]"
        ] = {}
        self.has_errored = Event()

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
            try:
                app = app_class(env=self.env)
            except Exception:
                self.has_errored.set()
                raise
            self.apps[name] = app
            processing_queue: (
                "Queue[List[Tuple[AggregateEvent[Aggregate], ProcessEvent]]]"
            ) = Queue(maxsize=self.processing_queue_size)
            self.processing_queues[name] = processing_queue
            processing_thread = ProcessingThread(
                processing_queue=processing_queue,
                follower=app,
                has_errored=self.has_errored,
            )
            processing_thread.start()
            self.processing_threads[name] = processing_thread
            self.pulling_threads[name] = {}

        # Construct non-follower leaders.
        for name in self.system.leaders_only:
            self.apps[name] = self.system.leader_cls(name)(env=self.env)

        # Lead and follow.
        for edge in self.system.edges:
            leader_name = edge[0]
            leader = self.apps[leader_name]
            follower_name = edge[1]
            follower = self.apps[follower_name]
            assert isinstance(leader, Leader)
            assert isinstance(follower, Follower)
            follower.follow(leader.__class__.__name__, leader.log)
            prompted_event = Event()
            pulling_thread = PullingThread(
                processing_queue=self.processing_queues[follower_name],
                prompted_event=prompted_event,
                follower=follower,
                leader_name=leader_name,
                has_errored=self.has_errored,
            )
            pulling_thread.start()
            self.pulling_threads[follower_name][leader_name] = pulling_thread
            leader.lead(pulling_thread)

    def watch_for_errors(self) -> None:
        self.has_errored.wait()
        self.stop()

    def stop(self) -> None:
        self.apps.clear()
        self.reraise_thread_errors()

    def reraise_thread_errors(self) -> None:
        for d in self.pulling_threads.values():
            for pulling in d.values():
                if pulling.error:
                    raise PullingThreadError(*pulling.error.args) from pulling.error
        for processing in self.processing_threads.values():
            if processing.error:
                raise ProcessingThreadError(
                    *processing.error.args
                ) from processing.error

    def get(self, cls: Type[A]) -> A:
        app = self.apps[cls.__name__]
        assert isinstance(app, cls)
        return app


class PullingThread(Promptable, Thread):
    """
    A pulling thread is a :class:`~eventsourcing.system.Promptable`
    object, and implements the :func:`receive_prompt` method by setting
    its 'prompted_event'. When the event is set event notifications
    are pulled from the leader, using the appropriate notification log
    reader in the follower application. Events are placed on a processing
    queue.
    """

    def __init__(
        self,
        processing_queue: "Queue[List[Tuple[AggregateEvent[Aggregate], ProcessEvent]]]",
        prompted_event: Event,
        follower: Follower[Aggregate],
        leader_name: str,
        has_errored: Event,
    ):
        super().__init__(daemon=True)
        self.prompted_event = prompted_event
        self.processing_queue = processing_queue
        self.follower = follower
        self.leader_name = leader_name
        self.error: Optional[Exception] = None
        self.has_errored = has_errored

    def run(self) -> None:
        last_notification_id = self.follower.recorder.max_tracking_id(self.leader_name)
        try:
            while True:
                self.prompted_event.wait()
                seen_nothing = False
                while not seen_nothing:
                    self.prompted_event.clear()
                    start = last_notification_id + 1
                    job = list(self.follower.pull_events(self.leader_name, start))
                    if len(job):
                        self.processing_queue.put(job)
                        process_event = job[-1][1]
                        assert process_event.tracking is not None
                        last_notification_id = process_event.tracking.notification_id
                    else:
                        seen_nothing = True
        except Exception as e:
            self.error = e
            self.has_errored.set()

    def receive_prompt(self, leader_name: str) -> None:
        self.prompted_event.set()


class ProcessingThread(Thread):
    """
    A processing thread gets events from a processing queue, and
    calls the application's process_event() method.
    """

    def __init__(
        self,
        processing_queue: "Queue[List[Tuple[AggregateEvent[Aggregate], ProcessEvent]]]",
        follower: Follower[Aggregate],
        has_errored: Event,
    ):
        super().__init__(daemon=True)
        self.processing_queue = processing_queue
        self.follower = follower
        self.error: Optional[Exception] = None
        self.has_errored = has_errored

    def run(self) -> None:
        try:
            while True:
                for domain_event, process_event in self.processing_queue.get():
                    self.follower.process_event(domain_event, process_event)
        except Exception as e:
            self.error = e
            self.has_errored.set()


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

    def select(
        self, *, start: int, topics: Sequence[str] = ()
    ) -> Iterator[Notification]:
        """
        Returns a generator that yields event notifications
        from the reader's notification log, starting from
        given start position (a notification ID).

        This method selects a limited list of notifications from a
        notification log and yields event notifications individually.
        When all the event notifications in the list are yielded,
        the reader will retrieve another list, and continue yielding
        event notification until all subsequent event notifications
        in the notification log from the start position have been
        yielded.
        """
        while True:
            notifications = self.notification_log.select(
                start, self.section_size, topics=topics
            )
            for notification in notifications:
                yield notification
            if len(notifications) < self.section_size:
                break
            else:
                start = notifications[-1].id + 1
