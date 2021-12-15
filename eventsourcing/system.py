from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from queue import Queue
from threading import Event, Lock, RLock, Thread
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
    Union,
    cast,
)

from eventsourcing.application import (
    Application,
    NotificationLog,
    ProcessEvent,
    Section,
    TApplication,
)
from eventsourcing.domain import Aggregate, AggregateEvent, TAggregate
from eventsourcing.persistence import (
    Mapper,
    Notification,
    ProcessRecorder,
    Tracking,
)
from eventsourcing.utils import EnvType, get_topic, resolve_topic

ProcessingJob = Tuple[AggregateEvent[Aggregate], Tracking]


class PullMode(ABC):
    @abstractmethod
    def chose_to_pull(self, received_id: int, expected_id: int) -> bool:
        """
        Decide whether to pull or not
        """


class AlwaysPull(PullMode):
    def chose_to_pull(self, received_id: int, expected_id: int) -> bool:
        return True


class PullGaps(PullMode):
    def chose_to_pull(self, received_id: int, expected_id: int) -> bool:
        return received_id != expected_id


class NeverPull(PullMode):
    def chose_to_pull(self, received_id: int, expected_id: int) -> bool:
        return False


class Follower(Application[TAggregate]):
    """
    Extends the :class:`~eventsourcing.application.Application` class
    by using a process recorder as its application recorder, by keeping
    track of the applications it is following, and pulling and processing
    new domain event notifications through its :func:`policy` method.
    """

    follow_topics: Sequence[str] = []
    pull_section_size = 10
    pull_mode: PullMode = AlwaysPull()

    def __init__(self, env: Optional[EnvType] = None) -> None:
        super().__init__(env)
        self.readers: Dict[str, NotificationLogReader] = {}
        self.mappers: Dict[str, Mapper] = {}
        self.recorder: ProcessRecorder
        self.is_threading_enabled = False
        self.processing_lock = RLock()

    def construct_recorder(self) -> ProcessRecorder:
        """
        Constructs and returns a :class:`~eventsourcing.persistence.ProcessRecorder`
        for the application to use as its application recorder.
        """
        return self.factory.process_recorder()

    def follow(self, name: str, log: NotificationLog) -> None:
        """
        Constructs a notification log reader and a mapper for
        the named application, and adds them to its collections
        of readers and mappers.
        """
        assert isinstance(self.recorder, ProcessRecorder)
        reader = NotificationLogReader(log, section_size=self.pull_section_size)
        env = self.construct_env(name, self.env)
        factory = self.construct_factory(env)
        mapper = factory.mapper(self.construct_transcoder())
        self.readers[name] = reader
        self.mappers[name] = mapper

    # @retry(IntegrityError, max_attempts=100)
    def pull_and_process(self, leader_name: str, start: Optional[int] = None) -> None:
        """
        Pull and process new domain event notifications.
        """
        if start is None:
            start = self.recorder.max_tracking_id(leader_name) + 1
        mapper = self.mappers[leader_name]
        for notifications in self.pull_notifications(leader_name, start=start):
            notifications_iter = self.filter_received_notifications(notifications)
            for domain_event, tracking in self.convert_notifications(
                mapper, leader_name, notifications_iter
            ):
                self.process_event(domain_event, tracking)

    def pull_notifications(
        self, leader_name: str, start: int
    ) -> Iterable[List[Notification]]:
        """
        Pulls batches of unseen :class:`~eventsourcing.persistence.Notification`
        objects from the notification log reader of the named application.
        """
        return self.readers[leader_name].select(start=start, topics=self.follow_topics)

    def filter_received_notifications(
        self, notifications: Iterable[Notification]
    ) -> Iterable[Notification]:
        if self.follow_topics:
            notifications = (n for n in notifications if n.topic in self.follow_topics)
        return notifications

    def convert_notifications(
        self, mapper: Mapper, name: str, notifications: Iterable[Notification]
    ) -> Iterable[ProcessingJob]:
        """
        Uses the given :class:`~eventsourcing.persistence.Mapper` to convert
        each received :class:`~eventsourcing.persistence.Notification`
        object to an :class:`~eventsourcing.domain.AggregateEvent` object
        paired with a :class:`~eventsourcing.persistence.Tracking` object.
        """
        for notification in notifications:
            domain_event = cast(
                AggregateEvent[Aggregate], mapper.to_domain_event(notification)
            )
            tracking = Tracking(
                application_name=name,
                notification_id=notification.id,
            )
            yield domain_event, tracking

    # @retry(IntegrityError, max_attempts=50000, wait=0.01)
    def process_event(
        self, domain_event: AggregateEvent[Aggregate], tracking: Tracking
    ) -> None:
        """
        Calls :func:`~eventsourcing.system.Follower.policy` method with
        the given :class:`~eventsourcing.domain.AggregateEvent` and a
        new :class:`~eventsourcing.application.ProcessEvent` created from
        the given :class:`~eventsourcing.persistence.Tracking` object.

        The policy will collect any new aggregate events on the process
        event object.

        After the policy method returns, the process event object will
        then be recorded by calling
        :func:`~eventsourcing.application.Application.record`, which
        will return new notifications.

        After calling
        :func:`~eventsourcing.application.Application.take_snapshots`,
        the new notifications are passed to the
        :func:`~eventsourcing.application.Application.notify` method.
        """
        process_event = ProcessEvent(tracking=tracking)
        with self.processing_lock:
            self.policy(domain_event, process_event)
            notifications = self.record(process_event)
            self.take_snapshots(process_event)
            self.notify(notifications)

    @abstractmethod
    def policy(
        self,
        domain_event: AggregateEvent[Aggregate],
        process_event: ProcessEvent,
    ) -> None:
        """
        Abstract domain event processing policy method. Must be
        implemented by event processing applications. When
        processing the given domain event, event processing
        applications must use the :func:`~ProcessEvent.collect_events`
        method of the given process event object (instead of
        the application's :func:`~eventsourcing.application.Application.save`
        method) to collect pending events from changed aggregates,
        so that the new domain events will be recorded atomically
        with tracking information about the position of the given
        domain event's notification.
        """

    def chose_to_pull(self, received_id: int, expected_id: int) -> bool:
        return self.pull_mode.chose_to_pull(received_id, expected_id)


class Promptable(ABC):
    """
    Abstract base class for "promptable" objects.
    """

    @abstractmethod
    def receive_notifications(
        self, leader_name: str, notifications: List[Notification]
    ) -> None:
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

    def notify(self, notifications: List[Notification]) -> None:
        """
        Extends the application :func:`~eventsourcing.application.Application.notify`
        method by calling :func:`notify_followers` whenever new events have just
        been saved.
        """
        super().notify(notifications)
        if notifications:
            self.notify_followers(notifications)

    def notify_followers(self, notifications: List[Notification]) -> None:
        """
        Prompts followers by calling their :func:`~Promptable.receive_prompt`
        methods with the name of the application.
        """
        for follower in self.followers:
            follower.receive_notifications(self.name, notifications)


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
        classes: Dict[str, Type[Application[Aggregate]]] = {}
        edges: Set[Tuple[str, str]] = set()
        # Build nodes and edges.
        for pipe in pipes:
            follower_cls = None
            for cls in pipe:
                classes[cls.name] = cls
                if follower_cls is None:
                    follower_cls = cls
                else:
                    leader_cls = follower_cls
                    follower_cls = cls
                    edges.add(
                        (
                            leader_cls.name,
                            follower_cls.name,
                        )
                    )

        self.edges = list(edges)
        self.nodes: Dict[str, str] = {}
        for name in classes:
            topic = get_topic(classes[name])
            self.nodes[name] = topic

        # Identify leaders and followers.
        self.follows: Dict[str, List[str]] = defaultdict(list)
        self.leads: Dict[str, List[str]] = defaultdict(list)
        for edge in edges:
            self.leads[edge[0]].append(edge[1])
            self.follows[edge[1]].append(edge[0])

        # Identify singles.
        self.singles = []
        for name in classes:
            if name not in self.leads and name not in self.follows:
                self.singles.append(name)

        # Check followers are followers.
        for name in self.follows:
            if not issubclass(classes[name], Follower):
                raise TypeError("Not a follower class: %s" % classes[name])

        # Check each process is a process application class.
        for name in self.processors:
            if not issubclass(classes[name], ProcessApplication):
                raise TypeError("Not a process application class: %s" % classes[name])

    @property
    def leaders(self) -> List[str]:
        return list(self.leads.keys())

    @property
    def leaders_only(self) -> List[str]:
        return [name for name in self.leads.keys() if name not in self.follows]

    @property
    def followers(self) -> List[str]:
        return list(self.follows.keys())

    @property
    def processors(self) -> List[str]:
        return [name for name in self.leads.keys() if name in self.follows]

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
                cls.name,
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
    def get(self, cls: Type[TApplication]) -> TApplication:
        """
        Returns an application instance for given application class.
        """


class RunnerAlreadyStarted(Exception):
    """
    Raised when runner is already started.
    """


class NotificationPullingError(Exception):
    """
    Raised when pulling notifications fails.
    """


class NotificationConvertingError(Exception):
    """
    Raised when converting notifications fails.
    """


class EventProcessingError(Exception):
    """
    Raised when event processing fails.
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
        self.notifications_received: Dict[str, List[Notification]] = {}
        self.notifications_received_lock = Lock()
        self.is_prompting = False
        self.is_prompting_lock = Lock()
        self.last_ids: Dict[Tuple[str, str], int] = {}
        # self.debug_received_notifications = set()

        # Construct followers.
        for name in self.system.followers:
            self.apps[name] = self.system.follower_cls(name)(env=self.env)

        # Construct leaders.
        for name in self.system.leaders_only:
            leader = self.system.leader_cls(name)(env=self.env)
            self.apps[name] = leader

        # Construct singles.
        for name in self.system.singles:
            single = self.system.get_app_cls(name)(env=self.env)
            self.apps[name] = single

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

        # Setup followers to follow leaders.
        for edge in self.system.edges:
            leader_name = edge[0]
            follower_name = edge[1]
            leader = cast(Leader[Aggregate], self.apps[leader_name])
            follower = cast(Follower[Aggregate], self.apps[follower_name])
            assert isinstance(leader, Leader)
            assert isinstance(follower, Follower)
            follower.follow(leader_name, leader.log)

        # Setup leaders to notify followers.
        for name in self.system.leaders:
            leader = cast(Leader[Aggregate], self.apps[name])
            assert isinstance(leader, Leader)
            leader.lead(self)

    def receive_notifications(
        self, leader_name: str, notifications: List[Notification]
    ) -> None:
        """
        Receives prompt by appending name of
        leader to list of prompted names.
        Unless this method has previously been called but not
        yet returned, it will then proceed to forward the prompts
        received to its application by calling the application's
        :func:`~Follower.pull_and_process` method for each prompted name.
        """
        with self.notifications_received_lock:
            if leader_name not in self.notifications_received:
                self.notifications_received[leader_name] = notifications
            else:
                self.notifications_received[leader_name] += notifications

            if self.is_prompting:
                return
            else:
                self.is_prompting = True

        while True:

            with self.notifications_received_lock:
                notifications_received, self.notifications_received = (
                    self.notifications_received,
                    {},
                )

                if not notifications_received:
                    self.is_prompting = False
                    return

            for leader_name, notifications in notifications_received.items():
                for follower_name in self.system.leads[leader_name]:
                    follower = self.apps[follower_name]
                    assert isinstance(follower, Follower)
                    last_id = self.last_ids.get((follower.name, leader_name))
                    if last_id is None:
                        last_id = follower.recorder.max_tracking_id(leader_name)
                    next_id = last_id + 1
                    mapper = follower.mappers[leader_name]
                    if follower.chose_to_pull(notifications[0].id, next_id):
                        for notifications in follower.pull_notifications(
                            leader_name, start=next_id
                        ):
                            self.filter_convert_process(
                                notifications, follower, leader_name, mapper
                            )

                    else:
                        # Process received notifications.
                        self.filter_convert_process(
                            notifications, follower, leader_name, mapper
                        )

    def filter_convert_process(
        self,
        notifications: List[Notification],
        follower: Follower[Aggregate],
        leader_name: str,
        mapper: Mapper,
    ) -> None:
        self.last_ids[(follower.name, leader_name)] = notifications[-1].id
        notifications_iter = follower.filter_received_notifications(notifications)
        jobs = follower.convert_notifications(mapper, leader_name, notifications_iter)
        for domain_event, tracking in jobs:
            follower.process_event(domain_event, tracking)

    def stop(self) -> None:
        for app in self.apps.values():
            app.close()
        self.apps.clear()

    def get(self, cls: Type[TApplication]) -> TApplication:
        app = self.apps[cls.name]
        assert isinstance(app, cls)
        return app


class MultiThreadedRunner(Runner, Promptable):
    """
    Runs a :class:`System` with a :class:`MultiThreadedRunnerThread` for each
    follower in the system definition.
    It is a runner, and so implements the :func:`start`, :func:`stop`,
    and :func:`get` methods.
    """

    QUEUE_MAX_SIZE: int = 0

    def __init__(
        self,
        system: System,
        env: Optional[EnvType] = None,
    ):
        """
        Initialises runner with the given :class:`System`.
        """
        super().__init__(system, env)
        self.apps: Dict[str, Application[Aggregate]] = {}
        self.pulling_threads: Dict[str, List[PullingThread]] = {}
        self.processing_queues: Dict[str, "Queue[Optional[List[ProcessingJob]]]"] = {}
        self.all_threads: List[
            Union[PullingThread, ConvertingThread, ProcessingThread]
        ] = []
        self.has_errored = Event()

        # Construct followers.
        for follower_name in self.system.followers:
            follower_class = self.system.follower_cls(follower_name)
            try:
                follower = follower_class(env=self.env)
            except Exception:
                self.has_errored.set()
                raise
            self.apps[follower_name] = follower

        # Construct non-follower leaders.
        for leader_name in self.system.leaders_only:
            self.apps[leader_name] = self.system.leader_cls(leader_name)(env=self.env)

        # Construct singles.
        for name in self.system.singles:
            single = self.system.get_app_cls(name)(env=self.env)
            self.apps[name] = single

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

        # Start the processing threads.
        for follower_name in self.system.followers:
            follower = cast(Follower[Aggregate], self.apps[follower_name])
            processing_queue: "Queue[Optional[List[ProcessingJob]]]" = Queue(
                maxsize=self.QUEUE_MAX_SIZE
            )
            self.processing_queues[follower_name] = processing_queue
            processing_thread = ProcessingThread(
                processing_queue=processing_queue,
                follower=follower,
                has_errored=self.has_errored,
            )
            self.all_threads.append(processing_thread)
            processing_thread.start()

        for edge in self.system.edges:
            # Set up follower to pull notifications from leader.
            leader_name = edge[0]
            leader = cast(Leader[Aggregate], self.apps[leader_name])
            follower_name = edge[1]
            follower = cast(Follower[Aggregate], self.apps[follower_name])
            follower.follow(leader.name, leader.log)

            # Create converting queue.
            prompted_event = Event()
            converting_queue: "Queue[Optional[List[Notification]]]" = Queue(
                maxsize=self.QUEUE_MAX_SIZE
            )

            # Start converting thread.
            converting_thread = ConvertingThread(
                converting_queue=converting_queue,
                processing_queue=self.processing_queues[follower_name],
                follower=follower,
                leader_name=leader_name,
                has_errored=self.has_errored,
            )
            self.all_threads.append(converting_thread)
            converting_thread.start()

            # Start pulling thread.
            pulling_thread = PullingThread(
                converting_queue=converting_queue,
                prompted_event=prompted_event,
                follower=follower,
                leader_name=leader_name,
                has_errored=self.has_errored,
            )
            self.all_threads.append(pulling_thread)
            pulling_thread.start()
            if leader_name not in self.pulling_threads:
                self.pulling_threads[leader_name] = []
            self.pulling_threads[leader_name].append(pulling_thread)

        # Wait until all the threads have started.
        for thread in self.all_threads:
            thread.has_started.wait()

        # Subscribe for notifications from leaders.
        for leader_name in self.system.leaders:
            leader = cast(Leader[Aggregate], self.apps[leader_name])
            assert isinstance(leader, Leader)
            leader.lead(self)

        # # Prompt to pull (catch up on start).
        # for thread in self.all_threads:
        #     if isinstance(thread, PullingThread):
        #         thread.prompted_event.set()

    def watch_for_errors(self, timeout: Optional[float] = None) -> bool:
        if self.has_errored.wait(timeout=timeout):
            self.stop()
        return self.has_errored.is_set()

    def stop(self) -> None:
        for thread in self.all_threads:
            thread.stop()
        for thread in self.all_threads:
            thread.join(timeout=2)
        for app in self.apps.values():
            app.close()
        self.apps.clear()
        self.reraise_thread_errors()

    def reraise_thread_errors(self) -> None:
        for thread in self.all_threads:
            if thread.error:
                raise thread.error

    def get(self, cls: Type[TApplication]) -> TApplication:
        app = self.apps[cls.name]
        assert isinstance(app, cls)
        return app

    def receive_notifications(
        self, leader_name: str, notifications: List[Notification]
    ) -> None:
        for pulling_thread in self.pulling_threads[leader_name]:
            pulling_thread.receive_notifications(notifications)


class PullingThread(Thread):
    """
    Receives or pulls notifications from the given leader, and
    puts them on a queue for conversion into processing jobs.
    """

    def __init__(
        self,
        converting_queue: "Queue[Optional[List[Notification]]]",
        prompted_event: Event,
        follower: Follower[Aggregate],
        leader_name: str,
        has_errored: Event,
    ):
        super().__init__(daemon=True)
        self.prompted_event = prompted_event
        self.converting_queue = converting_queue
        self.receive_lock = Lock()
        self.follower = follower
        self.leader_name = leader_name
        self.error: Optional[Exception] = None
        self.has_errored = has_errored
        self.is_stopping = Event()
        self.has_started = Event()
        self.mapper = self.follower.mappers[self.leader_name]
        self.last_id = self.follower.recorder.max_tracking_id(self.leader_name)

    def run(self) -> None:
        self.has_started.set()
        try:
            while self.prompted_event.wait() and not self.is_stopping.is_set():
                self.prompted_event.clear()
                with self.receive_lock:
                    # Pull notifications.
                    for notifications in self.follower.pull_notifications(
                        leader_name=self.leader_name, start=self.last_id + 1
                    ):
                        self.filter_and_queue(notifications)
        except Exception as e:
            self.error = NotificationPullingError(str(e))
            self.error.__cause__ = e
            self.has_errored.set()

    def receive_notifications(self, notifications: List[Notification]) -> None:
        if type(self.follower.pull_mode) is AlwaysPull:
            # Prompt to pull notifications.
            self.prompted_event.set()
        else:
            with self.receive_lock:
                # Decide whether to pull or process.
                if self.follower.chose_to_pull(notifications[0].id, self.last_id + 1):
                    # Prompt to pull notifications.
                    self.prompted_event.set()
                else:
                    # Process received notifications.
                    self.filter_and_queue(notifications)

    def filter_and_queue(self, notifications: List[Notification]) -> None:
        self.last_id = notifications[-1].id
        notifications = list(self.follower.filter_received_notifications(notifications))
        if len(notifications):
            self.converting_queue.put(notifications)

    def stop(self) -> None:
        self.is_stopping.set()
        self.prompted_event.set()


class ConvertingThread(Thread):
    """
    Converts notifications into processing jobs.
    """

    def __init__(
        self,
        converting_queue: "Queue[Optional[List[Notification]]]",
        processing_queue: "Queue[Optional[List[ProcessingJob]]]",
        follower: Follower[Aggregate],
        leader_name: str,
        has_errored: Event,
    ):
        super().__init__(daemon=True)
        self.converting_queue = converting_queue
        self.processing_queue = processing_queue
        self.follower = follower
        self.leader_name = leader_name
        self.error: Optional[Exception] = None
        self.has_errored = has_errored
        self.is_stopping = Event()
        self.has_started = Event()
        self.mapper = self.follower.mappers[self.leader_name]

    def run(self) -> None:
        self.has_started.set()
        try:
            while True:
                notifications = self.converting_queue.get()
                self.converting_queue.task_done()
                if self.is_stopping.is_set() or notifications is None:
                    return
                processing_jobs = list(
                    self.follower.convert_notifications(
                        self.mapper, self.leader_name, notifications
                    )
                )
                self.processing_queue.put(processing_jobs)
        except Exception as e:
            self.error = NotificationConvertingError(str(e))
            self.error.__cause__ = e
            self.has_errored.set()

    def stop(self) -> None:
        self.is_stopping.set()
        self.converting_queue.put(None)


class ProcessingThread(Thread):
    """
    A processing thread gets events from a processing queue, and
    calls the application's process_event() method.
    """

    def __init__(
        self,
        processing_queue: "Queue[Optional[List[ProcessingJob]]]",
        follower: Follower[Aggregate],
        has_errored: Event,
    ):
        super().__init__(daemon=True)
        self.processing_queue = processing_queue
        self.follower = follower
        self.error: Optional[Exception] = None
        self.has_errored = has_errored
        self.is_stopping = Event()
        self.has_started = Event()
        self.last_id = 0

    def run(self) -> None:
        self.has_started.set()
        try:
            while True:
                jobs = self.processing_queue.get()
                if self.is_stopping.is_set() or jobs is None:
                    return
                self.processing_queue.task_done()
                for domain_event, tracking in jobs:
                    self.follower.process_event(domain_event, tracking)
                    self.last_id = tracking.notification_id
        except Exception as e:
            self.error = EventProcessingError(str(e))
            self.error.__cause__ = e
            self.has_errored.set()

    def stop(self) -> None:
        self.is_stopping.set()
        self.processing_queue.put(None)


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
    ) -> Iterator[List[Notification]]:
        """
        Returns a generator that yields lists of event notifications
        from the reader's notification log, starting from given start
        position (a notification ID).

        This method selects a limited list of notifications from a
        notification log and yields event notifications in batches.
        When one list of event notifications has been yielded,
        the reader will retrieve another list, and continue until
        all subsequent event notifications in the notification log
        from the start position have been yielded.
        """
        while True:
            notifications = self.notification_log.select(
                start, self.section_size, topics=topics
            )
            if notifications:
                yield notifications
                start = notifications[-1].id + 1
            else:
                break
