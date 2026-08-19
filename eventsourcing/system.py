from __future__ import annotations

import inspect
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from types import FrameType, ModuleType
from typing import TYPE_CHECKING, Any, ClassVar, cast, override

from eventsourcing.application import (
    AggregatesApplication,
    NotificationLog,
    Section,
)
from eventsourcing.errors import ProgrammingError
from eventsourcing.metadata import null_metadata_in_context
from eventsourcing.persistence import (
    AggregateEventMapper,
    ApplicationRecorder,
    Notification,
    ProcessRecorder,
    Tracking,
)
from eventsourcing.projection import EventSourcedEventProcessor
from eventsourcing.types import (
    EventCollectorProtocol,
    EventEnvelopeProtocol,
)
from eventsourcing.utils import EnvType, get_topic, resolve_topic

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence
    from types import TracebackType
    from typing import Self

    from eventsourcing.domain import AggregateEvent

type ProcessingJob[TEnvelope: EventEnvelopeProtocol[Any]] = tuple[TEnvelope, Tracking]


class Follower[TDecision](EventSourcedEventProcessor[TDecision]):
    """Extends the :class:`~eventsourcing.projection.EventSourcedProjection` class
    by pulling notification objects from its notification log readers, by converting
    the notification objects to domain events and tracking objects and by processing
    the reconstructed domain event objects.
    """

    pull_section_size = 10

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # for backwards compatibility, set "topics" if has "follow_topics".
        cls.topics = getattr(cls, "follow_topics", cls.topics)

    def __init__(self, *, env: EnvType | None = None, context_name: str | None = None):
        super().__init__(env=env, context_name=context_name)
        self.readers: dict[str, NotificationLogReader] = {}
        self.mappers: dict[str, AggregateEventMapper[TDecision]] = {}
        self.is_threading_enabled = False

    def follow(self, name: str, log: NotificationLog) -> None:
        """Constructs a notification log reader and a mapper for
        the named application, and adds them to its collections
        of readers and mappers.
        """
        assert isinstance(self.recorder, ProcessRecorder)
        reader = NotificationLogReader(log, section_size=self.pull_section_size)
        env = self.construct_env(name=name, env=self.env)
        factory = self.construct_factory(env)
        transcoder = self.construct_transcoder()
        transcoder.check_decision_type(self)
        mapper = factory.mapper(transcoder, mapper_class=type(self.mapper))
        self.readers[name] = reader
        self.mappers[name] = mapper

    # @retry(IntegrityError, max_attempts=100)
    def pull_and_process(
        self, leader_name: str, start: int | None = None, stop: int | None = None
    ) -> None:
        """Pull and process new domain event notifications."""
        if start is None:
            start = self.recorder.max_tracking_id(leader_name)
        for notifications in self.pull_notifications(
            leader_name, start=start, stop=stop, inclusive_of_start=False
        ):
            notifications_iter = self.filter_received_notifications(notifications)
            for domain_event, tracking in self.convert_notifications(
                leader_name, notifications_iter
            ):
                self.process_event(domain_event, tracking)

    @override
    def process_event(
        self,
        envelope: AggregateEvent[TDecision],
        tracking: Tracking,
    ) -> None:
        with self.processing_lock:
            super().process_event(envelope, tracking)

    def pull_notifications(
        self,
        leader_name: str,
        start: int | None,
        stop: int | None = None,
        *,
        inclusive_of_start: bool = True,
    ) -> Iterator[Sequence[Notification]]:
        """Pulls batches of unseen :class:`~eventsourcing.persistence.Notification`
        objects from the notification log reader of the named application.
        """
        return self.readers[leader_name].select(
            start=start,
            stop=stop,
            topics=self.topics,
            inclusive_of_start=inclusive_of_start,
        )

    def filter_received_notifications(
        self, notifications: Sequence[Notification]
    ) -> Sequence[Notification]:
        if self.topics:
            return [n for n in notifications if n.topic in self.topics]
        return notifications

    def convert_notifications(
        self, leader_name: str, notifications: Iterable[Notification]
    ) -> list[ProcessingJob[AggregateEvent[TDecision]]]:
        """Uses the given :class:`~eventsourcing.persistence.Mapper` to convert
        each received :class:`~eventsourcing.persistence.Notification`
        object to an :class:`~eventsourcing.domain.AggregateEvent` object
        paired with a :class:`~eventsourcing.persistence.Tracking` object.
        """
        mapper = self.mappers[leader_name]
        processing_jobs = []
        with null_metadata_in_context():
            for notification in notifications:
                envelope = mapper.to_domain_event(notification)
                tracking = Tracking(
                    context_name=leader_name,
                    notification_id=notification.id,
                )
                processing_jobs.append((envelope, tracking))
        return processing_jobs


class PromptReceiver[TDecision](ABC):
    """Abstract base class for objects that may receive recording events."""

    @abstractmethod
    def receive_prompt(self, context_name: str, notification_id: int) -> None:
        """Receives a notificcation ID prompt."""


class Leader[
    TRecorder: ApplicationRecorder,
    TDecision,
](
    AggregatesApplication[TRecorder, TDecision],
):
    """Extends the :class:`~eventsourcing.application.Application`
    class by also being responsible for keeping track of
    followers, and prompting followers when there are new
    domain event notifications to be pulled and processed.
    """

    def __init__(self, *, env: EnvType | None = None, context_name: str | None = None):
        super().__init__(env=env, context_name=context_name)
        self.previous_max_notification_id: int | None = None
        self.followers: list[PromptReceiver[TDecision]] = []

    def lead(self, follower: PromptReceiver[TDecision]) -> None:
        """Adds given follower to a list of followers."""
        self.followers.append(follower)

    @override
    def save(
        self,
        *objs: EventCollectorProtocol[AggregateEvent[TDecision]]
        | AggregateEvent[TDecision]
        | None,
        **kwargs: Any,
    ) -> int | None:
        if self.previous_max_notification_id is None:
            self.previous_max_notification_id = self.recorder.max_notification_id()
        return super().save(*objs, **kwargs)

    @override
    def _notify(self, notification_id: int | None) -> None:
        """Calls :func:`receive_recording_event` on each follower
        whenever new events have just been saved.
        """
        super()._notify(notification_id)
        if notification_id:
            for follower in self.followers:
                follower.receive_prompt(
                    context_name=self.context_name, notification_id=notification_id
                )


class ProcessApplication[
    TDecision,
](
    Follower[TDecision],
    Leader[ProcessRecorder, TDecision],
):
    """Base class for event processing applications
    that are both "leaders" and followers".
    """


class System:
    """Defines a system of applications."""

    __caller_modules: ClassVar[dict[int, ModuleType]] = {}

    def __init__(
        self,
        pipes: Iterable[Iterable[type[AggregatesApplication[Any, Any]]]],
    ):
        # Remember the caller frame's module, so that we might identify a topic.
        caller_frame = cast(FrameType, inspect.currentframe()).f_back
        module = cast(ModuleType, inspect.getmodule(caller_frame))
        type(self).__caller_modules[id(self)] = module  # noqa: SLF001

        # Build nodes and edges.
        self.edges: list[tuple[str, str]] = []
        classes: dict[str, type[AggregatesApplication[Any, Any]]] = {}
        for pipe in pipes:
            follower_cls = None
            for cls in pipe:
                classes[cls.context_name] = cls
                if follower_cls is None:
                    follower_cls = cls
                else:
                    leader_cls = follower_cls
                    follower_cls = cls
                    edge = (leader_cls.context_name, follower_cls.context_name)
                    if edge not in self.edges:
                        self.edges.append(edge)

        self.nodes: dict[str, str] = {}
        for name, cls in classes.items():
            self.nodes[name] = get_topic(cls)

        # Identify leaders and followers.
        self.follows: dict[str, list[str]] = defaultdict(list)
        self.leads: dict[str, list[str]] = defaultdict(list)
        for edge in self.edges:
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
                msg = f"Not a follower class: {classes[name]}"
                raise TypeError(msg)

        # Check each process is a process application class.
        for name in self.processors:
            if not issubclass(classes[name], ProcessApplication):
                msg = f"Not a process application class: {classes[name]}"
                raise TypeError(msg)

    @property
    def leaders(self) -> list[str]:
        return list(self.leads.keys())

    @property
    def leaders_only(self) -> list[str]:
        return [name for name in self.leads if name not in self.follows]

    @property
    def followers(self) -> list[str]:
        return list(self.follows.keys())

    @property
    def processors(self) -> list[str]:
        return [name for name in self.leads if name in self.follows]

    def get_app_cls(self, name: str) -> type[AggregatesApplication[Any, Any]]:
        cls = resolve_topic(self.nodes[name])
        assert issubclass(cls, AggregatesApplication)
        return cls

    def leader_cls(self, name: str) -> type[Leader[Any, Any]]:
        cls = self.get_app_cls(name)
        if issubclass(cls, Leader):
            return cls
        cls = type(cls.context_name, (Leader, cls), {})
        assert issubclass(cls, Leader)
        return cls

    def follower_cls(self, name: str) -> type[Follower[Any]]:
        cls = self.get_app_cls(name)
        assert issubclass(cls, Follower)
        return cls

    @property
    def topic(self) -> str:
        """
        Returns a topic to the system object, if constructed as a module attribute.
        """
        topic: str | None = None
        module = System.__caller_modules[id(self)]
        for name, value in module.__dict__.items():
            if value is self:
                topic = module.__name__ + ":" + name
                assert resolve_topic(topic) is self
        if topic is None:
            msg = f"Unable to compute topic for system object: {self}"
            raise ProgrammingError(msg)
        return topic


class Runner(ABC):
    """Abstract base class for system runners."""

    def __init__(self, system: System, env: EnvType | None = None):
        self.system = system
        self.env = env
        self.is_started = False

    @abstractmethod
    def start(self) -> None:
        """Starts the runner."""
        if self.is_started:
            raise RunnerAlreadyStartedError
        self.is_started = True

    @abstractmethod
    def stop(self) -> None:
        """Stops the runner."""

    @abstractmethod
    def get[T: AggregatesApplication[Any, Any]](self, cls: type[T]) -> T:
        """Returns an application instance for given application class."""

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        self.stop()
        return None


class RunnerAlreadyStartedError(Exception):
    """Raised when runner is already started."""


# class NotificationPullingError(Exception):
#     """Raised when pulling notifications fails."""


# class NotificationConvertingError(Exception):
#     """Raised when converting notifications fails."""


class EventProcessingError(Exception):
    """Raised when event processing fails."""


class SingleThreadedRunner[TDecision](Runner, PromptReceiver[TDecision]):
    """Runs a :class:`System` in a single thread."""

    def __init__(self, system: System, env: EnvType | None = None):
        """Initialises runner with the given :class:`System`."""
        super().__init__(system=system, env=env)
        self.apps: dict[str, AggregatesApplication[Any, Any]] = {}
        self._prompted_names_lock = threading.Lock()
        self._prompted_names: set[str] = set()
        self._processing_lock = threading.Lock()

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

    @override
    def start(self) -> None:
        """Starts the runner. The applications mentioned in the system definition
        are constructed. The followers are set up to follow the applications
        they are defined as following in the system definition. And the leaders
        are set up to lead the runner itself.
        """
        super().start()

        # Setup followers to follow leaders.
        for edge in self.system.edges:
            leader_name = edge[0]
            follower_name = edge[1]
            leader = cast("Leader[Any, Any]", self.apps[leader_name])
            follower = cast(Follower[Any], self.apps[follower_name])
            assert isinstance(leader, Leader)
            assert isinstance(follower, Follower)
            follower.follow(leader_name, leader.notification_log)

        # Setup leaders to lead this runner.
        for name in self.system.leaders:
            leader = cast("Leader[Any, Any]", self.apps[name])
            assert isinstance(leader, Leader)
            leader.lead(self)

    @override
    def receive_prompt(self, context_name: str, notification_id: int) -> None:
        """Receives prompt by appending the name of the leader
        to a list of prompted names.

        Then, unless this method has previously been called and not yet returned,
        each of the prompted names is resolved to a leader application, and its
        followers pull and process events from that application. This may lead to
        further names being added to the list of prompted names. This process
        continues until there are no more prompted names. In this way, a system
        of applications will process all events in a single thread.
        """
        leader_name = context_name
        with self._prompted_names_lock:
            self._prompted_names.add(leader_name)

        if self._processing_lock.acquire(blocking=False):
            try:
                while True:
                    with self._prompted_names_lock:
                        prompted_names = self._prompted_names
                        self._prompted_names = set()

                        if not prompted_names:
                            break

                    for leader_name in prompted_names:
                        for follower_name in self.system.leads[leader_name]:
                            follower = cast(Follower[Any], self.apps[follower_name])
                            follower.pull_and_process(leader_name)

            finally:
                self._processing_lock.release()

    @override
    def stop(self) -> None:
        for app in self.apps.values():
            app.close()
        self.apps.clear()

    @override
    def get[T: AggregatesApplication[Any, Any]](self, cls: type[T]) -> T:
        app = self.apps[cls.context_name]
        assert isinstance(app, cls)
        return app


class MultiThreadedRunner[TDecision](Runner):
    """Runs a :class:`System` with one :class:`MultiThreadedRunnerThread`
    for each :class:`Follower` in the system definition.
    """

    def __init__(self, system: System, env: EnvType | None = None):
        """Initialises runner with the given :class:`System`."""
        super().__init__(system=system, env=env)
        self.apps: dict[str, AggregatesApplication[Any, Any]] = {}
        self.threads: dict[str, MultiThreadedRunnerThread[TDecision]] = {}
        self.has_errored = threading.Event()

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

    @override
    def start(self) -> None:
        """Starts the runner.
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
        thread: MultiThreadedRunnerThread[TDecision]
        for follower_name in self.system.followers:
            follower = cast(Follower[Any], self.apps[follower_name])

            thread = MultiThreadedRunnerThread(
                follower=follower,
                has_errored=self.has_errored,
            )
            self.threads[follower.context_name] = thread
            thread.start()

        # Wait until all the threads have started.
        for thread in self.threads.values():
            thread.has_started.wait()

        # Lead and follow.
        for edge in self.system.edges:
            leader = cast("Leader[Any, Any]", self.apps[edge[0]])
            follower = cast(Follower[Any], self.apps[edge[1]])
            follower.follow(leader.context_name, leader.notification_log)
            thread = self.threads[follower.context_name]
            leader.lead(thread)

    def watch_for_errors(self, timeout: float | None = None) -> bool:
        if self.has_errored.wait(timeout=timeout):
            self.stop()
        return self.has_errored.is_set()

    @override
    def stop(self) -> None:
        threads = self.threads.values()
        for thread in threads:
            thread.stop()
        for thread in threads:
            thread.join(timeout=2)
        for app in self.apps.values():
            app.close()
        self.apps.clear()
        self.reraise_thread_errors()

    def reraise_thread_errors(self) -> None:
        for thread in self.threads.values():
            if thread.error:
                raise thread.error

    @override
    def get[T: AggregatesApplication[Any, Any]](self, cls: type[T]) -> T:
        app = self.apps[cls.context_name]
        assert isinstance(app, cls)
        return app


class MultiThreadedRunnerThread[TDecision](PromptReceiver[TDecision], threading.Thread):
    """Runs one :class:`~eventsourcing.system.Follower` application in
    a :class:`~eventsourcing.system.MultiThreadedRunner`.
    """

    def __init__(
        self,
        follower: Follower[TDecision],
        has_errored: threading.Event,
    ):
        super().__init__(daemon=True)
        self.follower = follower
        self.has_errored = has_errored
        self.error: Exception | None = None
        self.is_stopping = threading.Event()
        self.has_started = threading.Event()
        self.is_prompted = threading.Event()
        self.prompted_names: list[str] = []
        self.prompted_names_lock = threading.Lock()
        self.is_running = threading.Event()

    @override
    def run(self) -> None:
        """Loops forever until stopped. The loop blocks on waiting
        for the 'is_prompted' event to be set, then calls
        :func:`~Follower.pull_and_process` method for each
        prompted name.
        """
        self.has_started.set()

        try:
            while not self.is_stopping.is_set():
                self.is_prompted.wait()

                with self.prompted_names_lock:
                    prompted_names = self.prompted_names
                    self.prompted_names = []
                    self.is_prompted.clear()
                for name in prompted_names:
                    self.follower.pull_and_process(name)
        except Exception as e:
            self.error = EventProcessingError(str(e))
            self.error.__cause__ = e
            self.has_errored.set()

    @override
    def receive_prompt(self, context_name: str, notification_id: int) -> None:
        """Receives prompt by appending name of
        leader to list of prompted names.
        """
        leader_name = context_name
        with self.prompted_names_lock:
            if leader_name not in self.prompted_names:
                self.prompted_names.append(leader_name)
            self.is_prompted.set()

    def stop(self) -> None:
        self.is_stopping.set()
        self.is_prompted.set()


class NotificationLogReader:
    """Reads domain event notifications from a notification log."""

    DEFAULT_SECTION_SIZE = 10

    def __init__(
        self,
        notification_log: NotificationLog,
        section_size: int = DEFAULT_SECTION_SIZE,
    ):
        """Initialises a reader with the given notification log,
        and optionally a section size integer which determines
        the requested number of domain event notifications in
        each section retrieved from the notification log.
        """
        self.notification_log = notification_log
        self.section_size = section_size

    def read(self, *, start: int) -> Iterator[Notification]:
        """Returns a generator that yields event notifications
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
        section_id = f"{start},{start + self.section_size - 1}"
        while True:
            section: Section = self.notification_log[section_id]
            yield from section.items
            if section.next_id is None:
                break
            else:
                section_id = section.next_id

    def select(
        self,
        *,
        start: int | None,
        stop: int | None = None,
        topics: Sequence[str] = (),
        inclusive_of_start: bool = True,
    ) -> Iterator[Sequence[Notification]]:
        """Returns a generator that yields lists of event notifications
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
                start=start,
                stop=stop,
                limit=self.section_size,
                topics=topics,
                inclusive_of_start=inclusive_of_start,
            )
            # Stop if zero notifications.
            if len(notifications) == 0:
                break

            # Otherwise, yield and continue.
            start = notifications[-1].id
            if inclusive_of_start:
                start += 1
            yield notifications
