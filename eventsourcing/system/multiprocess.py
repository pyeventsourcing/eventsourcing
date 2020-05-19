import multiprocessing
from multiprocessing import Manager
from queue import Empty, Queue
from time import sleep
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple, Type

from eventsourcing.application.notificationlog import RecordManagerNotificationLog
from eventsourcing.application.popo import PopoApplication
from eventsourcing.application.process import ProcessApplication, PromptToQuit
from eventsourcing.application.simple import (
    ApplicationWithConcreteInfrastructure,
    Prompt,
    PromptToPull,
    is_prompt_to_pull,
)
from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.events import subscribe, unsubscribe
from eventsourcing.exceptions import (
    CausalDependencyFailed,
    OperationalError,
    ProgrammingError,
    RecordConflictError,
)
from eventsourcing.infrastructure.base import DEFAULT_PIPELINE_ID
from eventsourcing.system.definition import AbstractSystemRunner, System
from eventsourcing.system.runner import DEFAULT_POLL_INTERVAL, PromptOutbox


class MultiprocessRunner(AbstractSystemRunner):
    def __init__(
        self,
        system: System,
        pipeline_ids: Sequence[int] = (DEFAULT_PIPELINE_ID,),
        poll_interval: Optional[int] = None,
        setup_tables: bool = False,
        sleep_for_setup_tables: int = 0,
        **kwargs: Any
    ):
        super(MultiprocessRunner, self).__init__(system=system, **kwargs)
        self.pipeline_ids = pipeline_ids
        self.poll_interval = poll_interval or DEFAULT_POLL_INTERVAL
        assert isinstance(system, System)
        self.setup_tables = setup_tables or system.setup_tables
        self.sleep_for_setup_tables = sleep_for_setup_tables
        self.os_processes: List[OperatingSystemProcess] = []

    def start(self) -> None:
        self.os_processes = []

        self.manager = Manager()

        if TYPE_CHECKING:
            self.inboxes: Dict[Tuple[int, str], Queue[Prompt]]
            self.outboxes: Dict[Tuple[int, str], PromptOutbox[Tuple[int, str]]]
        self.inboxes = {}
        self.outboxes = {}

        # Setup queues.
        for pipeline_id in self.pipeline_ids:
            for process_name, upstream_names in self.system.upstream_names.items():
                inbox_id = (pipeline_id, process_name.lower())
                if inbox_id not in self.inboxes:
                    self.inboxes[inbox_id] = self.manager.Queue()
                for upstream_class_name in upstream_names:
                    outbox_id = (pipeline_id, upstream_class_name.lower())
                    if outbox_id not in self.outboxes:
                        self.outboxes[outbox_id] = PromptOutbox()
                    if inbox_id not in self.outboxes[outbox_id].downstream_inboxes:
                        self.outboxes[outbox_id].downstream_inboxes[
                            inbox_id
                        ] = self.inboxes[inbox_id]

        # Check we have the infrastructure classes we need.
        for process_class in self.system.process_classes.values():
            if not isinstance(process_class, ApplicationWithConcreteInfrastructure):
                if not self.infrastructure_class:
                    raise ProgrammingError("infrastructure_class is not set")
                elif issubclass(self.infrastructure_class, PopoApplication):
                    raise ProgrammingError("Can't use %s with %s" % (
                        type(self), self.infrastructure_class
                    ))
                elif not issubclass(
                    self.infrastructure_class, ApplicationWithConcreteInfrastructure
                ):
                    raise ProgrammingError(
                        "infrastructure_class is not a subclass of {}".format(
                            ApplicationWithConcreteInfrastructure
                        )
                    )

        # Subscribe to broadcast prompts published by a process
        # application in the parent operating system process.
        subscribe(handler=self.broadcast_prompt, predicate=is_prompt_to_pull)

        # Start operating system process.
        expect_tables_exist = False
        for pipeline_id in self.pipeline_ids:
            for process_name, upstream_names in self.system.upstream_names.items():
                process_class = self.system.process_classes[process_name]
                inbox = self.inboxes[(pipeline_id, process_name.lower())]
                outbox = self.outboxes.get((pipeline_id, process_name.lower()))
                os_process = OperatingSystemProcess(
                    application_process_class=process_class,
                    infrastructure_class=self.infrastructure_class,
                    upstream_names=upstream_names,
                    poll_interval=self.poll_interval,
                    pipeline_id=pipeline_id,
                    setup_tables=self.setup_tables,
                    inbox=inbox,
                    outbox=outbox,
                )
                os_process.daemon = True
                os_process.start()
                self.os_processes.append(os_process)
                if self.setup_tables and not expect_tables_exist:
                    # Avoid conflicts when creating tables.
                    sleep(self.sleep_for_setup_tables)
                    expect_tables_exist = True

        # Construct process applications in local process.
        for process_class in self.system.process_classes.values():
            self.get(process_class)

    def broadcast_prompt(self, prompt: PromptToPull) -> None:
        outbox_id = (prompt.pipeline_id, prompt.process_name)
        outbox = self.outboxes.get(outbox_id)
        if outbox:
            outbox.put(prompt)

    def close(self) -> None:
        super(MultiprocessRunner, self).close()

        unsubscribe(handler=self.broadcast_prompt, predicate=is_prompt_to_pull)

        for os_process in self.os_processes:
            os_process.inbox.put(PromptToQuit())

        for os_process in self.os_processes:
            os_process.join(timeout=10)

        for os_process in self.os_processes:
            if os_process.is_alive():
                os_process.terminate()

        self.os_processes.clear()


class OperatingSystemProcess(multiprocessing.Process):
    def __init__(
        self,
        application_process_class: Type[ProcessApplication],
        infrastructure_class: Type[ApplicationWithConcreteInfrastructure],
        upstream_names: List[str],
        inbox: Queue,
        outbox: Optional[PromptOutbox[Tuple[int, str]]] = None,
        pipeline_id: int = DEFAULT_PIPELINE_ID,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        setup_tables: bool = False,
        *args: Any,
        **kwargs: Any
    ):
        super(OperatingSystemProcess, self).__init__(*args, **kwargs)
        self.application_process_class = application_process_class
        self.infrastructure_class = infrastructure_class
        self.upstream_names = upstream_names
        self.daemon = True
        self.pipeline_id = pipeline_id
        self.poll_interval = poll_interval
        self.inbox = inbox
        self.outbox = outbox
        self.setup_tables = setup_tables

    def run(self) -> None:
        # Construct process application class.
        process_class = self.application_process_class
        if not isinstance(process_class, ApplicationWithConcreteInfrastructure):
            if self.infrastructure_class:
                process_class = process_class.mixin(self.infrastructure_class)
            else:
                raise ProgrammingError("infrastructure_class is not set")

        # Construct process application object.
        self.process: ProcessApplication = process_class(
            pipeline_id=self.pipeline_id, setup_table=self.setup_tables
        )

        # Follow upstream notification logs.
        for upstream_name in self.upstream_names:

            # Obtain a notification log object (local or remote) for the upstream
            # process.
            if upstream_name == self.process.name:
                # Upstream is this process's application,
                # so use own notification log.
                notification_log = self.process.notification_log
            else:
                # For a different application, we need to construct a notification
                # log with a record manager that has the upstream application ID.
                # Currently assumes all applications are using the same database
                # and record manager class. If it wasn't the same database,we would
                # to use a remote notification log, and upstream would need to provide
                # an API from which we can pull. It's not unreasonable to have a fixed
                # number of application processes connecting to the same database.
                record_manager = self.process.event_store.record_manager

                notification_log = RecordManagerNotificationLog(
                    record_manager=record_manager.clone(
                        application_name=upstream_name,
                        # Todo: Check if setting pipeline_id is necessary (it's the
                        #  same?).
                        pipeline_id=self.pipeline_id,
                    ),
                    section_size=self.process.notification_log_section_size,
                )
                # Todo: Support upstream partition IDs different from self.pipeline_id?
                # Todo: Support combining partitions. Read from different partitions
                #  but write to the same partition,
                # could be one os process that reads from many logs of the same
                # upstream app, or many processes each
                # reading one partition with contention writing to the same partition).
                # Todo: Support dividing partitions Read from one but write to many.
                #  Maybe one process per
                # upstream partition, round-robin to pick partition for write. Or
                # have many processes reading
                # with each taking it in turn to skip processing somehow.
                # Todo: Dividing partitions would allow a stream to flow at the same
                #  rate through slower
                # process applications.
                # Todo: Support merging results from "replicated state machines" -
                #  could have a command
                # logging process that takes client commands and presents them in a
                # notification log.
                # Then the system could be deployed in different places, running
                # independently, receiving
                # the same commands, and running the same processes. The command
                # logging process could
                # be accompanied with a result logging process that reads results
                # from replicas as they
                # are available. Not sure what to do if replicas return different
                # things. If one replica
                # goes down, then it could resume by pulling events from another? Not
                # sure what to do.
                # External systems could be modelled as commands.

            # Make the process follow the upstream notification log.
            self.process.follow(upstream_name, notification_log)

        # Subscribe to broadcast prompts published by the process application.
        subscribe(handler=self.broadcast_prompt, predicate=is_prompt_to_pull)

        try:
            self.loop_on_prompts()
        finally:
            unsubscribe(handler=self.broadcast_prompt, predicate=is_prompt_to_pull)

    @retry(CausalDependencyFailed, max_attempts=100, wait=0.1)
    def loop_on_prompts(self) -> None:

        # Run once, in case prompts were missed.
        self.run_process()

        # Loop on getting prompts.
        while True:
            try:
                # Todo: Make the poll interval gradually increase if there are only
                #  timeouts?
                item = self.inbox.get(timeout=self.poll_interval)
                self.inbox.task_done()

                if isinstance(item, PromptToQuit):
                    self.process.close()
                    break

                elif isinstance(item, PromptToPull):
                    self.run_process(item)

                else:
                    raise ProgrammingError("Unsupported prompt: {}".format(item))

            except Empty:
                # Basically, we're polling after a timeout.
                self.run_process()

    @retry((OperationalError, RecordConflictError), max_attempts=100, wait=0.1)
    def run_process(self, prompt: Optional[Prompt] = None) -> None:
        self.process.run(prompt)

    def broadcast_prompt(self, prompt: PromptToPull) -> None:
        if self.outbox is not None:
            self.outbox.put(prompt)
