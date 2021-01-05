from threading import Event, Thread
from typing import Dict, List, Type

from eventsourcing.application import Application
from eventsourcing.processapplication import (
    Follower,
    Leader,
    Promptable,
)
from eventsourcing.system import A, AbstractRunner


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
            follower.follow(
                leader.__class__.__name__, leader.log
            )
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
            raise TypeError(
                "Not a follower: %s" % app_class
            )
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
