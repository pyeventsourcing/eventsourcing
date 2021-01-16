from abc import ABC, abstractmethod
from collections import defaultdict
from threading import Event, Thread
from typing import Dict, Iterable, List, Set, Tuple, Type, TypeVar

from eventsourcing.application import (
    AbstractNotificationLog,
    Application,
    Section,
)
from eventsourcing.domain import Aggregate
from eventsourcing.persistence import (
    ApplicationRecorder,
    Mapper,
    Notification,
    ProcessRecorder,
    Tracking,
)
from eventsourcing.utils import get_topic, resolve_topic


class ProcessEvent:
    def __init__(self, tracking: Tracking):
        self.tracking = tracking
        self.events: List[Aggregate.Event] = []

    def collect(self, aggregates: List[Aggregate]):
        for aggregate in aggregates:
            self.events += aggregate._collect_()

    def save(self, *aggregates: Aggregate):
        for aggregate in aggregates:
            self.events += aggregate._collect_()


class Promptable(ABC):
    @abstractmethod
    def receive_prompt(self, leader_name: str) -> None:
        pass


class Follower(Promptable, Application):
    def __init__(self):
        super().__init__()
        self.readers: Dict[
            str,
            Tuple[
                NotificationLogReader,
                Mapper[Aggregate.Event],
            ],
        ] = {}

    def construct_recorder(self) -> ApplicationRecorder:
        return self.factory.process_recorder()

    def follow(self, name: str, log: AbstractNotificationLog):
        assert isinstance(self.recorder, ProcessRecorder)
        reader = NotificationLogReader(log)
        mapper = self.construct_mapper(name)
        self.readers[name] = (reader, mapper)

    def receive_prompt(self, leader_name: str) -> None:
        self.pull_and_process(leader_name)

    def pull_and_process(self, name: str) -> None:
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

    def record(self, process_event: ProcessEvent) -> None:
        self.events.put(
            **process_event.__dict__,
        )
        self.notify(process_event.events)

    @abstractmethod
    def policy(
        self,
        domain_event: Aggregate.Event,
        process_event: ProcessEvent,
    ):
        pass


class Leader(Application):
    def __init__(self):
        super().__init__()
        self.followers: List[Promptable] = []

    def lead(self, follower: Promptable):
        self.followers.append(follower)

    def notify(self, new_events: List[Aggregate.Event]):
        super().notify(new_events)
        if len(new_events):
            self.prompt_followers()

    def prompt_followers(self):
        name = self.__class__.__name__
        for follower in self.followers:
            follower.receive_prompt(name)


class ProcessApplication(Leader, Follower):
    pass


class System:
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
                raise TypeError("Not a follower class: %s" % nodes[name])

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

    def get_app_cls(self, name) -> Type[Application]:
        cls = resolve_topic(self.nodes[name])
        assert issubclass(cls, Application)
        return cls

    def leader_cls(self, name) -> Type[Leader]:
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

    def follower_cls(self, name) -> Type[Follower]:
        cls = self.get_app_cls(name)
        assert issubclass(cls, Follower)
        return cls


A = TypeVar("A")


class AbstractRunner:
    def __init__(self, system: System):
        self.system = system
        self.is_started = False

    @abstractmethod
    def start(self) -> None:
        if self.is_started:
            raise self.AlreadyStarted()
        self.is_started = True

    class AlreadyStarted(Exception):
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def get(self, cls: Type[A]) -> A:
        pass


class SingleThreadedRunner(Promptable, AbstractRunner):
    def __init__(self, system: System):
        super(SingleThreadedRunner, self).__init__(system)
        self.apps: Dict[str, Application] = {}
        self.prompts_received: List[str] = []
        self.is_prompting = False

    def start(self):
        super().start()

        # Construct followers.
        for name in self.system.followers:
            app = self.system.follower_cls(name)()
            self.apps[name] = app

        # Construct leaders.
        for name in self.system.leaders_only:
            app = self.system.leader_cls(name)()
            self.apps[name] = app

        # Lead and follow.
        for edge in self.system.edges:
            leader = self.apps[edge[0]]
            follower = self.apps[edge[1]]
            assert isinstance(leader, Leader)
            assert isinstance(follower, Follower)
            leader.lead(self)
            follower.follow(leader.__class__.__name__, leader.log)

    def receive_prompt(self, leader_name: str) -> None:
        if leader_name not in self.prompts_received:
            self.prompts_received.append(leader_name)
        if not self.is_prompting:
            self.is_prompting = True
            while self.prompts_received:
                prompt = self.prompts_received.pop(0)
                for name in self.system.leads[prompt]:
                    follower = self.apps[name]
                    assert isinstance(follower, Follower)
                    follower.receive_prompt(prompt)
            self.is_prompting = False

    def stop(self):
        self.apps.clear()

    def get(self, cls: Type[A]) -> A:
        app = self.apps[cls.__name__]
        assert isinstance(app, cls)
        return app


class MultiThreadedRunner(AbstractRunner):
    """
    Runs system with thread for each follower.
    """

    def __init__(self, system):
        super().__init__(system)
        self.apps: Dict[str, Application] = {}
        self.threads: Dict[str, RunnerThread] = {}
        self.is_stopping = Event()

    def start(self) -> None:
        super().start()

        # Construct followers.
        for name in self.system.followers:
            thread = RunnerThread(
                app_class=self.system.follower_cls(name),
                is_stopping=self.is_stopping,
            )
            thread.start()
            thread.is_ready.wait(timeout=1)
            self.threads[name] = thread
            self.apps[name] = thread.app

        # Construct leaders.
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

    def stop(self):
        self.is_stopping.set()
        for thread in self.threads.values():
            thread.is_prompted.set()
            thread.join()

    def get(self, cls: Type[A]) -> A:
        app = self.apps[cls.__name__]
        assert isinstance(app, cls)
        return app


class RunnerThread(Promptable, Thread):
    def __init__(
        self,
        app_class: Type[Follower],
        is_stopping: Event,
    ):
        super(RunnerThread, self).__init__()
        if not issubclass(app_class, Follower):
            raise TypeError("Not a follower: %s" % app_class)
        self.app_class = app_class
        self.is_stopping = is_stopping
        self.is_prompted = Event()
        self.prompted_names: List[str] = []
        self.setDaemon(True)
        self.is_ready = Event()

    def run(self):
        try:
            self.app: Follower = self.app_class()
        except:
            self.is_stopping.set()
            raise
        self.is_ready.set()
        while True:
            self.is_prompted.wait()
            if self.is_stopping.is_set():
                return
            self.is_prompted.clear()
            while self.prompted_names:
                name = self.prompted_names.pop(0)
                self.app.pull_and_process(name)

    def receive_prompt(self, leader_name: str) -> None:
        self.prompted_names.append(leader_name)
        self.is_prompted.set()


class NotificationLogReader:
    DEFAULT_SECTION_SIZE = 10

    def __init__(
        self,
        notification_log: AbstractNotificationLog,
        section_size: int = DEFAULT_SECTION_SIZE,
    ):
        self.notification_log = notification_log
        self.section_size = section_size

    def read(self, *, start: int) -> Iterable[Notification]:
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
