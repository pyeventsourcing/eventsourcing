import os
from threading import Event, Thread
from time import sleep
from typing import List, Optional, Type

import ray

from eventsourcing.application.notificationlog import RecordManagerNotificationLog
from eventsourcing.application.process import (
    ProcessApplication,
    Prompt,
    is_prompt,
    PromptToPull,
)
from eventsourcing.application.simple import ApplicationWithConcreteInfrastructure
from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.events import subscribe, unsubscribe
from eventsourcing.exceptions import ProgrammingError, RecordConflictError
from eventsourcing.infrastructure.base import DEFAULT_PIPELINE_ID
from eventsourcing.system.definition import AbstractSystemRunner, System
from eventsourcing.system.runner import DEFAULT_POLL_INTERVAL

ray.init()


def start_ray_system():
    pass
    # ray.init(ignore_reinit_error=True)


def shutdown_ray_system():
    pass
    # ray.shutdown()


class RayRunner(AbstractSystemRunner):
    """
    Uses actor model framework to run a system of process applications.
    """

    def __init__(
        self,
        system: System,
        pipeline_ids=(DEFAULT_PIPELINE_ID,),
        poll_interval: Optional[int] = None,
        setup_tables: bool = False,
        sleep_for_setup_tables: int = 0,
        db_uri: str = None,
        **kwargs
    ):
        super(RayRunner, self).__init__(system=system, **kwargs)
        self.pipeline_ids = list(pipeline_ids)
        self.poll_interval = poll_interval
        self.setup_tables = setup_tables or system.setup_tables
        self.sleep_for_setup_tables = sleep_for_setup_tables
        self.db_uri = db_uri
        self.ray_processes = {}

    def start(self):
        """
        Starts all the actors to run a system of process applications.
        """

        # Check we have the infrastructure classes we need.
        for process_class in self.system.process_classes.values():
            if not isinstance(process_class, ApplicationWithConcreteInfrastructure):
                if not self.infrastructure_class:
                    raise ProgrammingError("infrastructure_class is not set")
                elif not issubclass(
                    self.infrastructure_class, ApplicationWithConcreteInfrastructure
                ):
                    raise ProgrammingError(
                        "infrastructure_class is not a subclass of {}".format(
                            ApplicationWithConcreteInfrastructure
                        )
                    )

        expect_tables_exist = False

        # Start processes.
        for pipeline_id in self.pipeline_ids:
            for process_name, process_class in self.system.process_classes.items():
                ray_process_id = RayProcess.remote(
                    application_process_class=process_class,
                    infrastructure_class=self.infrastructure_class,
                    env_vars={"DB_URI": self.db_uri},
                    poll_interval=self.poll_interval,
                    pipeline_id=pipeline_id,
                    setup_tables=self.setup_tables,
                )
                self.ray_processes[(process_name, pipeline_id)] = ray_process_id
                if self.setup_tables and not expect_tables_exist:
                    # Avoid conflicts when creating tables.
                    sleep(self.sleep_for_setup_tables)
                    # expect_tables_exist = True

        for key, ray_process in self.ray_processes.items():
            process_name, pipeline_id = key
            upstream_names = self.system.upstream_names[process_name]
            downstream_names = self.system.downstream_names[process_name]
            upstream_processes = {
                name: self.ray_processes[(name, pipeline_id)] for name in upstream_names
            }
            downstream_processes = {
                name: self.ray_processes[(name, pipeline_id)]
                for name in downstream_names
            }
            ray_process.run.remote(upstream_processes, downstream_processes)

    def get_process(self, process_name, pipeline_id=DEFAULT_PIPELINE_ID):
        assert isinstance(process_name, str)
        return self.ray_processes[(process_name, pipeline_id)]

    def close(self):
        super(RayRunner, self).close()
        processes = self.ray_processes.values()
        stop_ids = [p.stop.remote() for p in processes]
        ray.get(stop_ids)


@ray.remote
class RayProcess:
    def __init__(
        self,
        application_process_class: Type[ProcessApplication],
        infrastructure_class: Type[ApplicationWithConcreteInfrastructure],
        env_vars: dict = None,
        pipeline_id: int = DEFAULT_PIPELINE_ID,
        poll_interval: int = None,
        setup_tables: bool = False,
    ):
        self.application_process_class = application_process_class
        self.infrastructure_class = infrastructure_class
        self.daemon = True
        self.pipeline_id = pipeline_id
        self.poll_interval = poll_interval or DEFAULT_POLL_INTERVAL
        self.setup_tables = setup_tables
        self.prompted_event = Event()
        self.prompted_names = set()
        self.stopped_event = Event()
        if env_vars is not None:
            os.environ.update(env_vars)
        self.process = None

    def call(self, application_method_name, *args, **kwargs):
        if self.process:
            method = getattr(self.process, application_method_name)
            return method(*args, **kwargs)
        else:
            raise Exception("Can't call method '%s' before process exists" % application_method_name)

    def prompt(self, prompt: List[Prompt] = None):
        # print("Received prompt: ", prompt)
        # sleep(0.1)

        if isinstance(prompt, list):
            prompt = prompt[0]
        if prompt:
            if isinstance(prompt, PromptToPull):
                self.prompted_names.add(prompt.process_name)
        self.prompted_event.set()

    def stop(self):
        self.stopped_event.set()
        self.prompt()
        unsubscribe(handler=self.broadcast_prompt, predicate=is_prompt)

    def broadcast_prompt(self, prompt):
        # Todo: Something to prompt followers.
        # print("Broadcasting prompt ", prompt)
        # sleep(0.1)
        for ray_process in self.downstream_processes.values():
            ray_process.prompt.remote(prompt)
            # ray.get(ray_process.prompt.remote(prompt))

    def run(self, upstream_processes, downstream_processes) -> None:
        print("Running ray process")
        self.upstream_processes = upstream_processes
        self.downstream_processes = downstream_processes

        # Subscribe to broadcast prompts published by the process application.
        subscribe(handler=self.broadcast_prompt, predicate=is_prompt)

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

        print("Constructed application process")


        # Follow upstream notification logs.
        for upstream_name, upstream_process in self.upstream_processes.items():

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

            # Make the process follow the upstream notification log.
            self.process.follow(upstream_name, notification_log)

        self.run_thread = Thread(target=self.loop_on_prompts)
        self.run_thread.start()

    def loop_on_prompts(self) -> None:
        # Run once, in case there is already something to process.
        self.run_process()

        # Loop on getting prompts.
        while True:
            if self.prompted_event.wait(timeout=self.poll_interval):
                if self.stopped_event.is_set():
                    break
                prompted_names = self.prompted_names.copy()
                for process_name in prompted_names:
                    self.prompted_names.remove(process_name)
                self.prompted_event.clear()
                for process_name in prompted_names:
                    prompt = PromptToPull(process_name, self.pipeline_id)
                    # print(prompt)
                    self.run_process(prompt)

                    if self.stopped_event.is_set():
                        break
            else:
                if self.stopped_event.is_set():
                    break
                self.run_process()
            sleep(0.0)

    def run_process(self, prompt: Optional[Prompt] = None) -> None:
        try:
            self._run_process(prompt)
        except Exception as e:
            print("Error running process: ", e)

    @retry(RecordConflictError, max_attempts=10, wait=0.05)
    def _run_process(self, prompt: Optional[Prompt] = None) -> None:
        # print("Running process application...")
        self.process.run(prompt)
