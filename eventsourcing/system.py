from __future__ import annotations

import traceback
from abc import ABC, abstractmethod
from collections import defaultdict
from queue import Full, Queue
from threading import Event, Lock, RLock, Thread
from typing import (
    Any,
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

from eventsourcing.application import ProcessEvent  # noqa: F401
from eventsourcing.application import (
    Application,
    NotificationLog,
    ProcessingEvent,
    RecordingEvent,
    Section,
    TApplication,
)
from eventsourcing.domain import DomainEvent
from eventsourcing.persistence import (
    IntegrityError,
    Mapper,
    Notification,
    ProcessRecorder,
    Recording,
    Tracking,
)
from eventsourcing.utils import EnvType, get_topic, resolve_topic

ProcessingJob = Tuple[DomainEvent[Any], Tracking]
ConvertingJob = Optional[Union[RecordingEvent, List[Notification]]]


class Follower(Application):
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
    def pull_and_process(
        self, leader_name: str, start: Optional[int] = None, stop: Optional[int] = None
    ) -> None:
        """
        Pull and process new domain event notifications.
        """
        if start is None:
            start = self.recorder.max_tracking_id(leader_name) + 1
        for notifications in self.pull_notifications(
            leader_name, start=start, stop=stop
        ):
            notifications_iter = self.filter_received_notifications(notifications)
            for domain_event, tracking in self.convert_notifications(
                leader_name, notifications_iter
            ):
                self.process_event(domain_event, tracking)

    def pull_notifications(
        self, leader_name: str, start: int, stop: Optional[int] = None
    ) -> Iterator[List[Notification]]:
        """
        Pulls batches of unseen :class:`~eventsourcing.persistence.Notification`
        objects from the notification log reader of the named application.
        """
        return self.readers[leader_name].select(
            start=start, stop=stop, topics=self.follow_topics
        )

    def filter_received_notifications(
        self, notifications: List[Notification]
    ) -> List[Notification]:
        if self.follow_topics:
            return [n for n in notifications if n.topic in self.follow_topics]
        else:
            return notifications

    def convert_notifications(
        self, leader_name: str, notifications: Iterable[Notification]
    ) -> List[ProcessingJob]:
        """
        Uses the given :class:`~eventsourcing.persistence.Mapper` to convert
        each received :class:`~eventsourcing.persistence.Notification`
        object to an :class:`~eventsourcing.domain.AggregateEvent` object
        paired with a :class:`~eventsourcing.persistence.Tracking` object.
        """
        mapper = self.mappers[leader_name]
        processing_jobs = []
        for notification in notifications:
            domain_event = mapper.to_domain_event(notification)
            tracking = Tracking(
                application_name=leader_name,
                notification_id=notification.id,
            )
            processing_jobs.append((domain_event, tracking))
        return processing_jobs

    # @retry(IntegrityError, max_attempts=50000, wait=0.01)
    def process_event(self, domain_event: DomainEvent[Any], tracking: Tracking) -> None:
        """
        Calls :func:`~eventsourcing.system.Follower.policy` method with
        the given :class:`~eventsourcing.domain.AggregateEvent` and a
        new :class:`~eventsourcing.application.ProcessingEvent` created from
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
        processing_event = ProcessingEvent(tracking=tracking)
        with self.processing_lock:
            self.policy(domain_event, processing_event)
            try:
                recordings = self._record(processing_event)
            except IntegrityError:
                if tracking.notification_id <= self.recorder.max_tracking_id(
                    tracking.application_name
                ):
                    pass
                else:
                    raise
            else:
                self._take_snapshots(processing_event)
                self.notify(processing_event.events)
                self._notify(recordings)

    @abstractmethod
    def policy(
        self,
        domain_event: DomainEvent[Any],
        processing_event: ProcessingEvent,
    ) -> None:
        """
        Abstract domain event processing policy method. Must be
        implemented by event processing applications. When
        processing the given domain event, event processing
        applications must use the :func:`~ProcessingEvent.collect_events`
        method of the given process event object (instead of
        the application's :func:`~eventsourcing.application.Application.save`
        method) to collect pending events from changed aggregates,
        so that the new domain events will be recorded atomically
        with tracking information about the position of the given
        domain event's notification.
        """


class RecordingEventReceiver(ABC):
    """
    Abstract base class for objects that may receive recording events.
    """

    @abstractmethod
    def receive_recording_event(self, recording_event: RecordingEvent) -> None:
        """
        Receives a recording event.
        """


class Leader(Application):
    """
    Extends the :class:`~eventsourcing.application.Application`
    class by also being responsible for keeping track of
    followers, and prompting followers when there are new
    domain event notifications to be pulled and processed.
    """

    def __init__(self, env: Optional[EnvType] = None) -> None:
        super().__init__(env)
        self.followers: List[RecordingEventReceiver] = []

    def lead(self, follower: RecordingEventReceiver) -> None:
        """
        Adds given follower to a list of followers.
        """
        self.followers.append(follower)

    def _notify(self, recordings: List[Recording]) -> None:
        """
        Calls :func:`receive_recording_event` on each follower
        whenever new events have just been saved.
        """
        super()._notify(recordings)
        if self.notify_topics:
            recordings = [
                r for r in recordings if r.notification.topic in self.notify_topics
            ]
        if recordings:
            recording_event = RecordingEvent(
                application_name=self.name,
                recordings=recordings,
                previous_max_notification_id=self.previous_max_notification_id,
            )
            self.previous_max_notification_id = recordings[-1].notification.id
            for follower in self.followers:
                follower.receive_recording_event(recording_event)


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
        classes: Dict[str, Type[Application]] = {}
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
                cls.name,
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


class SingleThreadedRunner(Runner, RecordingEventReceiver):
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
        self.apps: Dict[str, Application] = {}
        self._recording_events_received: List[RecordingEvent] = []
        self._recording_events_received_lock = Lock()
        self._processing_lock = Lock()
        self._previous_max_notification_ids: Dict[str, int] = {}

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
            leader = cast(Leader, self.apps[leader_name])
            follower = cast(Follower, self.apps[follower_name])
            assert isinstance(leader, Leader)
            assert isinstance(follower, Follower)
            follower.follow(leader_name, leader.notification_log)

        # Setup leaders to notify followers.
        for name in self.system.leaders:
            leader = cast(Leader, self.apps[name])
            assert isinstance(leader, Leader)
            leader.lead(self)

    def receive_recording_event(self, recording_event: RecordingEvent) -> None:
        """
        Receives recording event by appending it to list of received recording
        events.

        Unless this method has previously been called and not yet returned, it
        will then attempt to make the followers process all received recording
        events, until there are none remaining.
        """
        with self._recording_events_received_lock:
            self._recording_events_received.append(recording_event)

        if self._processing_lock.acquire(blocking=False):
            try:
                while True:
                    with self._recording_events_received_lock:
                        recording_events_received = self._recording_events_received
                        self._recording_events_received = []

                        if not recording_events_received:
                            break

                    for recording_event in recording_events_received:
                        leader_name = recording_event.application_name
                        previous_max_notification_id = (
                            self._previous_max_notification_ids.get(leader_name, 0)
                        )

                        # Ignore recording event if already seen a subsequent.
                        if (
                            recording_event.previous_max_notification_id is not None
                            and recording_event.previous_max_notification_id
                            < previous_max_notification_id
                        ):
                            continue

                        # Catch up if there is a gap in sequence of recording events.
                        if (
                            recording_event.previous_max_notification_id is None
                            or recording_event.previous_max_notification_id
                            > previous_max_notification_id
                        ):
                            for follower_name in self.system.leads[leader_name]:
                                follower = self.apps[follower_name]
                                assert isinstance(follower, Follower)
                                start = (
                                    follower.recorder.max_tracking_id(leader_name) + 1
                                )
                                stop = recording_event.recordings[0].notification.id - 1
                                follower.pull_and_process(
                                    leader_name=leader_name,
                                    start=start,
                                    stop=stop,
                                )
                        for recording in recording_event.recordings:
                            for follower_name in self.system.leads[leader_name]:
                                follower = self.apps[follower_name]
                                assert isinstance(follower, Follower)
                                if (
                                    follower.follow_topics
                                    and recording.notification.topic
                                    not in follower.follow_topics
                                ):
                                    continue
                                follower.process_event(
                                    domain_event=recording.domain_event,
                                    tracking=Tracking(
                                        application_name=recording_event.application_name,
                                        notification_id=recording.notification.id,
                                    ),
                                )

                        self._previous_max_notification_ids[
                            leader_name
                        ] = recording_event.recordings[-1].notification.id

            finally:
                self._processing_lock.release()

    def stop(self) -> None:
        for app in self.apps.values():
            app.close()
        self.apps.clear()

    def get(self, cls: Type[TApplication]) -> TApplication:
        app = self.apps[cls.name]
        assert isinstance(app, cls)
        return app


class MultiThreadedRunner(Runner, RecordingEventReceiver):
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
        self.apps: Dict[str, Application] = {}
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
            follower = cast(Follower, self.apps[follower_name])
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
            leader = cast(Leader, self.apps[leader_name])
            follower_name = edge[1]
            follower = cast(Follower, self.apps[follower_name])
            follower.follow(leader.name, leader.notification_log)

            # Create converting queue.
            converting_queue: "Queue[ConvertingJob]" = Queue(
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
            leader = cast(Leader, self.apps[leader_name])
            assert isinstance(leader, Leader)
            leader.lead(self)

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

    def receive_recording_event(self, recording_event: RecordingEvent) -> None:
        for pulling_thread in self.pulling_threads[recording_event.application_name]:
            pulling_thread.receive_recording_event(recording_event)


class PullingThread(Thread):
    """
    Receives or pulls notifications from the given leader, and
    puts them on a queue for conversion into processing jobs.
    """

    def __init__(
        self,
        converting_queue: "Queue[ConvertingJob]",
        follower: Follower,
        leader_name: str,
        has_errored: Event,
    ):
        super().__init__(daemon=True)
        self.overflow_event = Event()
        self.recording_event_queue: "Queue[Optional[RecordingEvent]]" = Queue(
            maxsize=100
        )
        self.converting_queue = converting_queue
        self.receive_lock = Lock()
        self.follower = follower
        self.leader_name = leader_name
        self.error: Optional[Exception] = None
        self.has_errored = has_errored
        self.is_stopping = Event()
        self.has_started = Event()
        self.mapper = self.follower.mappers[self.leader_name]
        self.previous_max_notification_id = self.follower.recorder.max_tracking_id(
            application_name=self.leader_name
        )

    def run(self) -> None:
        self.has_started.set()
        try:
            while not self.is_stopping.is_set():
                recording_event = self.recording_event_queue.get()
                self.recording_event_queue.task_done()
                if recording_event is None:
                    return
                # Ignore recording event if already seen a subsequent.
                if (
                    recording_event.previous_max_notification_id is not None
                    and recording_event.previous_max_notification_id
                    < self.previous_max_notification_id
                ):
                    continue

                # Catch up if there is a gap in sequence of recording events.
                if (
                    recording_event.previous_max_notification_id is None
                    or recording_event.previous_max_notification_id
                    > self.previous_max_notification_id
                ):
                    start = self.previous_max_notification_id + 1
                    stop = recording_event.recordings[0].notification.id - 1
                    for notifications in self.follower.pull_notifications(
                        self.leader_name, start=start, stop=stop
                    ):
                        self.converting_queue.put(notifications)
                        self.previous_max_notification_id = notifications[-1].id
                self.converting_queue.put(recording_event)
                self.previous_max_notification_id = recording_event.recordings[
                    -1
                ].notification.id
        except Exception as e:
            self.error = NotificationPullingError(str(e))
            self.error.__cause__ = e
            self.has_errored.set()

    def receive_recording_event(self, recording_event: RecordingEvent) -> None:
        try:
            self.recording_event_queue.put(recording_event, timeout=0)
        except Full:
            self.overflow_event.set()

    def stop(self) -> None:
        self.is_stopping.set()
        self.recording_event_queue.put(None)


class ConvertingThread(Thread):
    """
    Converts notifications into processing jobs.
    """

    def __init__(
        self,
        converting_queue: "Queue[ConvertingJob]",
        processing_queue: "Queue[Optional[List[ProcessingJob]]]",
        follower: Follower,
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
                recording_event_or_notifications = self.converting_queue.get()
                self.converting_queue.task_done()
                if (
                    self.is_stopping.is_set()
                    or recording_event_or_notifications is None
                ):
                    return

                processing_jobs = []

                if isinstance(recording_event_or_notifications, RecordingEvent):
                    recording_event = recording_event_or_notifications
                    for recording in recording_event.recordings:
                        if (
                            self.follower.follow_topics
                            and recording.notification.topic
                            not in self.follower.follow_topics
                        ):
                            continue
                        tracking = Tracking(
                            application_name=recording_event.application_name,
                            notification_id=recording.notification.id,
                        )
                        processing_jobs.append((recording.domain_event, tracking))
                else:
                    notifications = recording_event_or_notifications
                    processing_jobs = self.follower.convert_notifications(
                        leader_name=self.leader_name, notifications=notifications
                    )
                if processing_jobs:
                    self.processing_queue.put(processing_jobs)
        except Exception as e:
            print(traceback.format_exc())
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
        follower: Follower,
        has_errored: Event,
    ):
        super().__init__(daemon=True)
        self.processing_queue = processing_queue
        self.follower = follower
        self.error: Optional[Exception] = None
        self.has_errored = has_errored
        self.is_stopping = Event()
        self.has_started = Event()

    def run(self) -> None:
        self.has_started.set()
        try:
            while True:
                jobs = self.processing_queue.get()
                self.processing_queue.task_done()
                if self.is_stopping.is_set() or jobs is None:
                    return
                for domain_event, tracking in jobs:
                    self.follower.process_event(domain_event, tracking)
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
        section, and continues yielding event notification until all subsequent
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
        self, *, start: int, stop: Optional[int] = None, topics: Sequence[str] = ()
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
                start=start, stop=stop, limit=self.section_size, topics=topics
            )
            # Stop if zero notifications.
            if len(notifications) == 0:
                break

            # Otherwise yield and continue.
            yield notifications
            start = notifications[-1].id + 1
