from abc import ABC, abstractmethod
from typing import Dict, List, Tuple

from eventsourcing.domain import Aggregate
from eventsourcing.application import (
    AbstractNotificationLog, Application,
)
from eventsourcing.persistence import ApplicationRecorder, Mapper, Notification, \
    ProcessRecorder
from eventsourcing.notificationlogreader import (
    NotificationLogReader,
)
from eventsourcing.tracking import Tracking


class Promptable(ABC):
    @abstractmethod
    def receive_prompt(self, leader_name: str) -> None:
        pass


class ProcessEvent:
    def __init__(self, tracking: Tracking):
        self.tracking = tracking
        self.events: List[Aggregate.Event] = []

    def collect(self, aggregates: List[Aggregate]):
        for aggregate in aggregates:
            self.events += aggregate._collect_()


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

    def follow(
        self, name: str, log: AbstractNotificationLog
    ):
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
            domain_event = mapper.to_domain_event(
                notification
            )
            process_event = ProcessEvent(
                Tracking(  # type: ignore
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
