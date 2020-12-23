from typing import Dict, List, Type

from eventsourcing.processapplication import (
    Follower,
    Leader,
    Promptable,
)
from eventsourcing.application import Application
from eventsourcing.system import System
from eventsourcing.systemrunner import A, AbstractRunner


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
