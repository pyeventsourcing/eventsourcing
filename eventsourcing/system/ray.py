import os
import traceback
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Dict, List, Optional, Tuple, Type

import ray

from eventsourcing.application.process import (
    ProcessApplication,
    Prompt,
    PromptToPull,
    is_prompt,
)
from eventsourcing.application.simple import ApplicationWithConcreteInfrastructure
from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.events import subscribe, unsubscribe
from eventsourcing.exceptions import (
    OperationalError,
    ProgrammingError,
    RecordConflictError,
)
from eventsourcing.infrastructure.base import DEFAULT_PIPELINE_ID
from eventsourcing.system.definition import AbstractSystemRunner, System
from eventsourcing.system.rayhelpers import RayNotificationLog, RayPrompt, RayDbJob
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
        db_uri: Optional[str] = None,
        **kwargs
    ):
        super(RayRunner, self).__init__(system=system, **kwargs)
        self.pipeline_ids = list(pipeline_ids)
        self.poll_interval = poll_interval
        self.setup_tables = setup_tables or system.setup_tables
        self.sleep_for_setup_tables = sleep_for_setup_tables
        self.db_uri = db_uri
        self.ray_processes: Dict[Tuple[str, int], RayProcess] = {}

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

        # Get the DB_URI.
        # Todo: Support different URI for different application classes.
        env_vars = {}
        db_uri = self.db_uri or os.environ.get("DB_URI")

        if db_uri is not None:
            env_vars["DB_URI"] = db_uri

        assert env_vars.get(
            "DB_URI"
        ), "DB_URI not set: Ray runner doesn't work with in-memory database at the mo"

        # Start processes.
        for pipeline_id in self.pipeline_ids:
            for process_name, process_class in self.system.process_classes.items():
                ray_process_id = RayProcess.remote(
                    application_process_class=process_class,
                    infrastructure_class=self.infrastructure_class,
                    env_vars=env_vars,
                    poll_interval=self.poll_interval,
                    pipeline_id=pipeline_id,
                    setup_tables=self.setup_tables,
                )
                self.ray_processes[(process_name, pipeline_id)] = ray_process_id

        init_ids = []

        for key, ray_process in self.ray_processes.items():
            process_name, pipeline_id = key
            upstream_names = self.system.upstream_names[process_name]
            downstream_names = self.system.downstream_names[process_name]
            downstream_processes = {
                name: self.ray_processes[(name, pipeline_id)]
                for name in downstream_names
            }

            upstream_logs = {}
            for upstream_name in upstream_names:
                upstream_process = self.ray_processes[(upstream_name, pipeline_id)]
                notification_log = RayNotificationLog(upstream_process, 5, ray.get)
                upstream_logs[upstream_name] = notification_log

            init_ids.append(
                ray_process.init.remote(upstream_logs, downstream_processes)
            )

        ray.get(init_ids)

        run_ids = []
        for ray_process in self.ray_processes.values():
            run_ids.append(ray_process.run.remote())
        ray.get(run_ids)

    def get_ray_process(self, process_name, pipeline_id=DEFAULT_PIPELINE_ID):
        assert isinstance(process_name, str)
        return self.ray_processes[(process_name, pipeline_id)]

    def close(self):
        super(RayRunner, self).close()
        processes = self.ray_processes.values()
        stop_ids = [p.stop.remote() for p in processes]
        ray.get(stop_ids, timeout=6)

    def call(self, process_name, pipeline_id, method_name, *args, **kwargs):
        paxosprocess0 = self.get_ray_process(process_name, pipeline_id)
        ray_id = paxosprocess0.call.remote(method_name, *args, **kwargs)
        return ray.get(ray_id)


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
        # Process application args.
        self.application_process_class = application_process_class
        self.infrastructure_class = infrastructure_class
        self.daemon = True
        self.pipeline_id = pipeline_id
        self.poll_interval = poll_interval or DEFAULT_POLL_INTERVAL
        self.setup_tables = setup_tables
        if env_vars is not None:
            os.environ.update(env_vars)

        # Setup threads, queues, and threading events.
        self.readers_lock = Lock()
        self.has_been_prompted = Event()
        self.heads_lock = Lock()
        self.heads = {}
        self.positions_lock = Lock()
        self.positions = {}
        self.db_jobs_queue = Queue() #maxsize=1)
        self.downstream_prompt_queue = Queue() #maxsize=1)
        self.upstream_prompt_queue = Queue() #maxsize=1)
        self.upstream_event_queue = Queue() #maxsize=1)

        self.has_been_stopped = Event()
        self.db_jobs_thread = Thread(target=self.db_jobs)
        self.db_jobs_thread.setDaemon(True)
        self.db_jobs_thread.start()

        self.process_prompts_thread = Thread(target=self.process_prompts)
        self.process_prompts_thread.setDaemon(True)
        self.process_prompts_thread.start()

        self.process_events_thread = Thread(target=self.process_events)
        self.process_events_thread.setDaemon(True)
        self.process_events_thread.start()

        self.push_prompts_thread = Thread(target=self.push_prompts)
        self.push_prompts_thread.setDaemon(True)
        self.push_prompts_thread.start()

    def db_jobs(self):
        # print("Running do_jobs")
        while not self.has_been_stopped.is_set():
            try:
                item = self.db_jobs_queue.get(timeout=1)
                self.db_jobs_queue.task_done()
            except Empty:
                if self.has_been_stopped.is_set():
                    break
            else:
                if item is None or self.has_been_stopped.is_set():
                    break
                db_job = item
                # self.print_timecheck("Doing db job", item)
                try:
                    db_job.execute()
                except Exception as e:
                    print(traceback.format_exc())
                    self.print_timecheck("Continuing after error running DB job")
                # else:
                #     self.print_timecheck("Done db job", item)

    def init(self, upstream_logs: dict, downstream_processes: dict) -> None:
        self.upstream_logs = upstream_logs
        self.downstream_processes = downstream_processes

        # Subscribe to broadcast prompts published by the process application.
        subscribe(handler=self.enqueue_prompt, predicate=is_prompt)

        # Construct process application object.
        process_class = self.application_process_class
        if not isinstance(process_class, ApplicationWithConcreteInfrastructure):
            if self.infrastructure_class:
                process_class = process_class.mixin(self.infrastructure_class)
            else:
                raise ProgrammingError("infrastructure_class is not set")

        def construct_process():
            return process_class(pipeline_id=self.pipeline_id,
                             setup_table=self.setup_tables)

        self.process = self.do_db_job(construct_process, (), {})
        assert isinstance(self.process, ProcessApplication), self.process
        # print(getpid(), "Created application process: %s" % self.process)

        for upstream_name, ray_notification_log in self.upstream_logs.items():
            # Make the process follow the upstream notification log.
            self.process.follow(upstream_name, ray_notification_log)

        self.reset_readers()
        self.reset_positions()

    def do_db_job(self, method, args, kwargs):
        db_job = RayDbJob(method, args=args, kwargs=kwargs)
        self.db_jobs_queue.put(db_job)

        # if db_job.wait() is False:
        #     if self.has_been_stopped.is_set():
        #         raise ProcessHasStopped()
        #     else:
        #         raise Exception("Timed out waiting for DB job to finish:", db_job.method)
        db_job.wait()

        if db_job.error:
            raise db_job.error
        try:
            self.print_timecheck('db job delay:', db_job.delay)
            self.print_timecheck('db job duration:', db_job.duration)
        except AssertionError as e:
            print("Error:", e)

        # self.print_timecheck('db job result:', db_job.result)
        return db_job.result

    def reset_readers(self):
        self.do_db_job(
            self._reset_readers, (), {}
        )

    def _reset_readers(self):
        with self.readers_lock:
            for upstream_name in self.process.readers:
                self.process.set_reader_position_from_tracking_records(upstream_name)

    def reset_positions(self):
        self.do_db_job(
            self._reset_positions, (), {}
        )

    def _reset_positions(self):
        with self.positions_lock:
            for upstream_name in self.process.readers:
                recorded_position = self.process.get_recorded_position(upstream_name)
                self.positions[upstream_name] = recorded_position

    def print_timecheck(self, activity, *args):
        pass
        # process_name = self.application_process_class.__name__.lower()
        # print("Timecheck", datetime.datetime.now(), process_name, activity, *args)

    def add_downstream_process(self, downstream_name, ray_process_id):
        self.downstream_processes[downstream_name] = ray_process_id

    def follow(self, upstream_name, ray_notification_log):
        # print("Received follow: ", upstream_name, ray_notification_log)
        # self.tmpdict[upstream_name] = ray_notification_log
        self.process.follow(upstream_name, ray_notification_log)

    def enqueue_prompt(self, prompts):
        for prompt in prompts:
            print("Enqueing locally published prompt:", prompt)
            self.downstream_prompt_queue.put(prompt)

    def run(self) -> None:
        pass

    @retry(OperationalError, max_attempts=10, wait=0.1)
    def call(self, application_method_name, *args, **kwargs):
        # print("Calling", application_method_name, args, kwargs)
        if self.process:
            # return method(*args, **kwargs)
            method = getattr(self.process, application_method_name)
            return self.do_db_job(method, args, kwargs)
        else:
            raise Exception(
                "Can't call method '%s' before process exists" % application_method_name
            )

    @retry(OperationalError, max_attempts=10, wait=0.1)
    def get_notification_log_section(self, section_id):
        def get_log_section(section_id):
            return self.process.notification_log[section_id]

        section = self.do_db_job(get_log_section, [section_id], {})
        self.print_timecheck("section of notification log, items:", len(section.items))
        return section

    def prompt(self, prompt: Prompt) -> None:
        # self.print_timecheck("prompt received", prompt.process_name)
        # self.print_timecheck('putting upstream prompt on upstream prompt queue',
        #                      self.upstream_prompt_queue.qsize())
        if isinstance(prompt, RayPrompt):
            latest_head = prompt.head_notification_id
            if latest_head is not None:
                with self.heads_lock:
                    if prompt.process_name in self.heads:
                        current_head = self.heads[prompt.process_name]
                        if current_head < latest_head:
                            self.heads[prompt.process_name] = current_head
                    else:
                        self.heads[prompt.process_name] = latest_head

        self.upstream_prompt_queue.put(prompt)

        self.has_been_prompted.set()
        # self.print_timecheck('put upstream prompt on upstream prompt queue')

    def process_prompts(self) -> None:
        # Loop until stop event is set.
        while not self.has_been_stopped.is_set():

            try:
                item = self.upstream_prompt_queue.get() #timeout=3)
                self.upstream_prompt_queue.task_done()
            except Empty:
                if self.has_been_stopped.is_set():
                    break
                self.print_timecheck("upstream prompt queue TIMED OUT")

                upstream_names = self.upstream_logs.keys()
            else:
                if item is None or self.has_been_stopped.is_set():
                    break
                else:
                    prompt = item
                upstream_names = [prompt.process_name]

                # if isinstance(prompt, RayPrompt):
                # notifications = ray.get(prompt.notifications_rayid)
                # print("Notifications received:", [n["id"] for n in notifications])
                # for notification in notifications:
                #     notification_id = notification["id"]
                #     if notification_id and isinstance(notification_id, int):
                #         cache_key = (prompt.process_name, notification_id)
                #         self.notifications_cache[cache_key] = notification

            # sleep(0.5)

            for upstream_name in upstream_names:

                with self.heads_lock:
                    current_head = self.heads.get(upstream_name)
                    print("Current head:", self.pipeline_id, self.process.name, upstream_name, current_head)

                # Get the notifications.
                reader = self.process.readers[upstream_name]

                self.print_timecheck("reader position", upstream_name, reader.position)


                # notifications = []
                # next_position = reader.position + 1
                # while True:
                #     cache_key = (prompted_name, next_position)
                #     notification = self.notifications_cache.get(cache_key)
                #     print("Cached notification:", notification)
                #     if notification:
                #         # reader.position = next_position
                #         notifications.append(notification)
                #         next_position = next_position + 1
                #     else:
                #         break

                notifications = reader.read_list()

                if len(notifications):
                    position = notifications[-1]["id"]
                    with self.positions_lock:
                        self.positions[upstream_name] = position
                        print("Current position", self.pipeline_id, self.process.name,
                              upstream_name,
                              position)

                self.print_timecheck("obtained notifications", len(notifications), upstream_name)

                for notification in notifications:
                    # Check causal dependencies.
                    self.process.check_causal_dependencies(
                        upstream_name, notification.get("causal_dependencies")
                    )

                    # Get event from notification.
                    event = self.process.get_event_from_notification(notification)

                    self.print_timecheck("obtained event", event)

                    # Put the event on the queue.
                    self.print_timecheck('putting upstream event on upstream event '
                                         'queue',
                                         self.upstream_event_queue.qsize())
                    self.upstream_event_queue.put(
                        (event, notification["id"], upstream_name)
                    )
                    self.print_timecheck('put upstream event on upstream '
                                         'event queue')

    def process_events(self):
        while not self.has_been_stopped.is_set():
            try:
                item = self.upstream_event_queue.get() #timeout=5)
                self.upstream_event_queue.task_done()
            except Empty:
                if self.has_been_stopped.is_set():
                    break
            else:
                if item is None or self.has_been_stopped.is_set():
                    break
                else:
                    domain_event, notification_id, upstream_name = item
                try:
                    # print("Processing upstream event:", (domain_event,
                    # notification_id, upstream_name))

                    new_events, new_records = self.do_db_job(
                        method=self.process.process_upstream_event,
                        args=(domain_event, notification_id, upstream_name),
                        kwargs={},
                    )

                    # print("New events:", new_events)
                    self.print_timecheck("new events", len(new_events), new_events)

                except Exception as e:
                    # print(traceback.format_exc())
                    print("Error processing event. Resetting ray process... %s" % e)
                    self.reset_processing()
                else:
                    notifications = [
                        self.process.event_store.record_manager
                            .create_notification_from_record(
                            record
                        )
                        for record in new_records
                        if isinstance(record.notification_id, int)
                    ]

                    self.print_timecheck('processed event')

                    if new_events:
                        self.print_timecheck('putting notifications on downstream '
                                             'prompt queue',
                                             self.downstream_prompt_queue.qsize())
                        self.downstream_prompt_queue.put(notifications)
                        self.print_timecheck('put notifications on downstream prompt '
                                             'queue')

    def push_prompts(self) -> None:
        while not self.has_been_stopped.is_set():
            try:
                item = self.downstream_prompt_queue.get()  #timeout=1)
            except Empty:
                self.print_timecheck('timed out getting item from downstream prompt '
                                     'queue')
                if self.has_been_stopped.is_set():
                    break
            else:
                self.downstream_prompt_queue.task_done()
                self.print_timecheck('task done on downstream prompt queue')
                if item is None or self.has_been_stopped.is_set():
                    break
                elif isinstance(item, PromptToPull):
                    prompt = item
                else:
                    notifications = item
                    # notifications_rayid = ray.put(notifications)
                    if len(notifications):
                        head_notification_id = notifications[-1]['id']
                    else:
                        head_notification_id = None
                    prompt = RayPrompt(
                        self.process.name,
                        self.process.pipeline_id,
                        head_notification_id
                    )
                prompt_response_ids = []
                self.print_timecheck("pushing prompts", prompt)
                for downstream_name, ray_process in self.downstream_processes.items():
                    # print("Pushing prompt", prompt)
                    # sleep(1)
                    prompt_response_ids.append(ray_process.prompt.remote(prompt))
                    if self.has_been_stopped.is_set():
                        break
                ray.get(prompt_response_ids)

    def stop(self):
        self.has_been_stopped.set()

        self.upstream_prompt_queue.put(None)
        self.process_prompts_thread.join(timeout=3)

        self.upstream_event_queue.put(None)
        self.process_events_thread.join(timeout=3)

        self.downstream_prompt_queue.put(None)
        self.push_prompts_thread.join(timeout=3)

        self.db_jobs_queue.put(None)
        self.db_jobs_thread.join(timeout=3)
        unsubscribe(handler=self.enqueue_prompt, predicate=is_prompt)

@ray.remote
class __RayProcess:
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
        if env_vars is not None:
            os.environ.update(env_vars)

        self.has_been_stopped = Event()
        self.db_jobs_queue = Queue(maxsize=1)
        print("Starting do_jobs thread")
        self.db_jobs_thread = Thread(target=self.db_jobs)
        self.db_jobs_thread.setDaemon(True)
        self.db_jobs_thread.start()

        # self.prompted_names = set()
        # self.prompted_lock = Lock()
        # self.has_been_prompted = Event()
        # self.event_reading_lock = Lock()
        self.notifications_cache = {}

        # self.reset_readers()

    def prompt(self, prompt: Prompt):
        self.print_timecheck("prompt received", prompt.process_name)
        self.print_timecheck('putting upstream prompt on upstream prompt queue',
                             self.upstream_prompt_queue.qsize())
        self.upstream_prompt_queue.put(prompt)
        self.print_timecheck('put upstream prompt on upstream prompt queue')
        # print("Prompt received:", prompt)

    def reset_processing(self):
        with self.event_reading_lock:
            self.reset_readers()
            with self.upstream_event_queue.mutex:
                self.upstream_event_queue.queue.clear()
            with self.prompted_lock:
                for upstream_name in self.upstream_logs.keys():
                    self.prompted_names.add(upstream_name)
                self.has_been_prompted.set()

    def reset_readers(self):
        self.do_db_job(
            self._reset_readers, (), {}
        )

    def _reset_readers(self):
        for upstream_name in self.process.readers:
            self.process.set_reader_position_from_tracking_records(upstream_name)

    def run_process(self, prompt: Optional[Prompt] = None) -> None:
        try:
            self._run_process(prompt)
        except:
            print(
                traceback.format_exc() + "\nException was ignored so that actor can "
                                         "continue running."
            )

    @retry((RecordConflictError, OperationalError, KeyError), 50, wait=0.1)
    def _run_process(self, prompt: Optional[Prompt] = None) -> None:
        self.process.run(prompt)

    def stop(self):
        self.has_been_stopped.set()
        self.db_jobs_queue.put(None)
        self.upstream_prompt_queue.put(None)
        self.upstream_event_queue.put(None)
        self.downstream_prompt_queue.put(None)
        self.has_been_prompted.set()
        self.process_prompts_thread.join(timeout=3)
        self.push_prompts_thread.join(timeout=3)
        unsubscribe(handler=self.enqueue_prompt, predicate=is_prompt)
