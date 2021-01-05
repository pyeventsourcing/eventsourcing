from abc import abstractmethod
from collections import defaultdict
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Set,
    Tuple,
    Type, TypeVar,
)

from eventsourcing.utils import get_topic, resolve_topic
from eventsourcing.processapplication import (
    Follower,
    Leader,
    ProcessApplication, Promptable,
)
from eventsourcing.application import Application


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
        self.follows: Dict[str, List[str]] = defaultdict(
            list
        )
        self.leads: Dict[str, List[str]] = defaultdict(
            list
        )
        for edge in edges:
            self.leads[edge[0]].append(edge[1])
            self.follows[edge[1]].append(edge[0])

        # Check followers are followers.
        for name in self.follows:
            if not issubclass(nodes[name], Follower):
                raise TypeError(
                    "Not a follower class: %s"
                    % nodes[name]
                )

        # Check each process is a process application class.
        for name in self.processors:
            if not issubclass(
                nodes[name], ProcessApplication
            ):
                raise TypeError(
                    "Not a follower class: %s"
                    % nodes[name]
                )

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
        return set(self.leaders).intersection(
            self.followers
        )

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
            follower.follow(
                leader.__class__.__name__, leader.log
            )

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
