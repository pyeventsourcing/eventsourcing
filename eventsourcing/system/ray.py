import datetime
import os
import traceback
from inspect import ismethod
from queue import Empty, Queue
from threading import Event, Lock, Thread
from time import sleep
from typing import Dict, Optional, Tuple, Type

import ray

from eventsourcing.application.process import ProcessApplication
from eventsourcing.application.simple import (
    ApplicationWithConcreteInfrastructure,
    Prompt,
    PromptToPull,
    is_prompt_to_pull,
)
from eventsourcing.domain.model.decorators import retry
from eventsourcing.domain.model.events import subscribe, unsubscribe
from eventsourcing.exceptions import (
    EventSourcingError,
    ExceptionWrapper,
    OperationalError,
    ProgrammingError,
    RecordConflictError,
)
from eventsourcing.infrastructure.base import (
    DEFAULT_PIPELINE_ID,
    RecordManagerWithNotifications,
)
from eventsourcing.system.definition import (
    AbstractSystemRunner,
    System,
    TProcessApplication,
)
from eventsourcing.system.rayhelpers import RayDbJob, RayPrompt
from eventsourcing.system.raysettings import ray_init_kwargs
from eventsourcing.system.runner import DEFAULT_POLL_INTERVAL

ray.init(**ray_init_kwargs)

MAX_QUEUE_SIZE = 1
PAGE_SIZE = 20
MICROSLEEP = 0.000
PROMPT_WITH_NOTIFICATION_IDS = False
PROMPT_WITH_NOTIFICATION_OBJS = False
GREEDY_PULL_NOTIFICATIONS = True


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

            upstream_processes = {}
            for upstream_name in upstream_names:
                upstream_process = self.ray_processes[(upstream_name, pipeline_id)]
                upstream_processes[upstream_name] = upstream_process

            init_ids.append(
                ray_process.init.remote(upstream_processes, downstream_processes)
            )
        ray.get(init_ids)

    def get_ray_process(self, process_name, pipeline_id=DEFAULT_PIPELINE_ID):
        assert isinstance(process_name, str)
        return self.ray_processes[(process_name, pipeline_id)]

    def close(self):
        super(RayRunner, self).close()
        for process in self.ray_processes.values():
            process.stop.remote()

    def get(
        self, process_class: Type[TProcessApplication], pipeline_id=DEFAULT_PIPELINE_ID
    ) -> TProcessApplication:
        assert issubclass(process_class, ProcessApplication)
        process_name = process_class.create_name()
        ray_process = self.get_ray_process(process_name, pipeline_id)
        return ProcessApplicationProxy(ray_process)


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
        self._has_been_prompted = Event()
        self.heads_lock = Lock()
        self.heads = {}
        self.positions_lock = Lock()
        self.positions = {}
        self.positions_initialised = Event()
        self.db_jobs_queue = Queue(maxsize=MAX_QUEUE_SIZE)
        self.upstream_event_queue = Queue(maxsize=MAX_QUEUE_SIZE)
        self.downstream_prompt_queue = Queue()  # no maxsize, call() can put prompt

        self.has_been_stopped = Event()
        self.db_jobs_thread = Thread(target=self.db_jobs)
        self.db_jobs_thread.setDaemon(True)
        self.db_jobs_thread.start()

        self.process_prompts_thread = Thread(target=self._process_prompts)
        self.process_prompts_thread.setDaemon(True)
        self.process_prompts_thread.start()

        self.process_events_thread = Thread(target=self._process_events)
        self.process_events_thread.setDaemon(True)
        self.process_events_thread.start()

        self.push_prompts_thread = Thread(target=self._push_prompts)
        self.push_prompts_thread.setDaemon(True)
        self.push_prompts_thread.start()

        self._notification_rayids = {}
        self._prompted_notifications = {}

    def db_jobs(self):
        # print("Running do_jobs")
        while not self.has_been_stopped.is_set():
            try:
                item = self.db_jobs_queue.get()  # timeout=1)
                self.db_jobs_queue.task_done()
            except Empty:
                if self.has_been_stopped.is_set():
                    break
            else:
                if item is None or self.has_been_stopped.is_set():
                    break
                db_job: RayDbJob = item
                # self.print_timecheck("Doing db job", item)
                try:
                    db_job.execute()
                except Exception as e:
                    if db_job.error is None:
                        print(traceback.format_exc())
                        self._print_timecheck(
                            "Continuing after error running DB job:", e
                        )
                        sleep(1)
                # else:
                #     self.print_timecheck("Done db job", item)

    @retry((OperationalError, RecordConflictError), max_attempts=100, wait=0.01)
    def do_db_job(self, method, args, kwargs):
        db_job = RayDbJob(method, args=args, kwargs=kwargs)
        self.db_jobs_queue.put(db_job)
        db_job.wait()

        if db_job.error:
            raise db_job.error

        # self.print_timecheck("db job delay:", db_job.delay)
        # self.print_timecheck("db job duration:", db_job.duration)

        # self.print_timecheck('db job result:', db_job.result)
        return db_job.result

    def init(self, upstream_processes: dict, downstream_processes: dict) -> None:
        """
        Initialise with actor handles for upstream and downstream processes.

        Need to initialise after construction so that all handles exist.
        """
        self.upstream_processes = upstream_processes
        self.downstream_processes = downstream_processes

        # Subscribe to broadcast prompts published by the process application.
        subscribe(handler=self._enqueue_prompt_to_pull, predicate=is_prompt_to_pull)

        # Construct process application object.
        process_class = self.application_process_class
        if not isinstance(process_class, ApplicationWithConcreteInfrastructure):
            if self.infrastructure_class:
                process_class = process_class.mixin(self.infrastructure_class)
            else:
                raise ProgrammingError("infrastructure_class is not set")

        class MethodWrapper(object):
            def __init__(self, method):
                self.method = method

            def __call__(self, *args, **kwargs):
                try:
                    return self.method(*args, **kwargs)
                except EventSourcingError as e:
                    return ExceptionWrapper(e)

        class ProcessApplicationWrapper(object):
            def __init__(self, process_application):
                self.process_application = process_application

            def __getattr__(self, item):
                attribute = getattr(self.process_application, item)
                if ismethod(attribute):
                    return MethodWrapper(attribute)
                else:
                    return attribute

        def construct_process():
            return process_class(
                pipeline_id=self.pipeline_id, setup_table=self.setup_tables
            )

        process_application = self.do_db_job(construct_process, (), {})
        assert isinstance(process_application, ProcessApplication), process_application
        self.process_wrapper = ProcessApplicationWrapper(process_application)
        self.process_application = process_application

        for upstream_name, ray_notification_log in self.upstream_processes.items():
            # Make the process follow the upstream notification log.
            self.process_application.follow(upstream_name, ray_notification_log)

        self._reset_positions()
        self.positions_initialised.set()

    def _reset_positions(self):
        self.do_db_job(self.__reset_positions, (), {})

    def __reset_positions(self):
        with self.positions_lock:
            for upstream_name in self.upstream_processes:
                recorded_position = self.process_application.get_recorded_position(
                    upstream_name
                )
                self.positions[upstream_name] = recorded_position

    def add_downstream_process(self, downstream_name, ray_process_id):
        self.downstream_processes[downstream_name] = ray_process_id

    def call(self, method_name, *args, **kwargs):
        """
        Method for calling methods on process application object.
        """
        assert self.positions_initialised.is_set(), "Please call .init() first"
        # print("Calling", method_name, args, kwargs)
        if self.process_wrapper:
            method = getattr(self.process_wrapper, method_name)
            return self.do_db_job(method, args, kwargs)
        else:
            raise Exception(
                "Can't call method '%s' before process exists" % method_name
            )

    def prompt(self, prompt: RayPrompt) -> None:
        assert isinstance(prompt, RayPrompt), "Not a RayPrompt: %s" % prompt
        for notification_id, rayid in prompt.notification_ids:
            # self._print_timecheck("Received ray notification ID:", notification_id, rayid)
            self._notification_rayids[(prompt.process_name, notification_id)] = rayid

        latest_head = prompt.head_notification_id
        upstream_name = prompt.process_name
        if PROMPT_WITH_NOTIFICATION_OBJS:
            for notification in prompt.notifications:
                self._prompted_notifications[
                    (upstream_name, notification["id"])
                ] = notification
        if latest_head is not None:
            with self.heads_lock:
                # Update head from prompt.
                if upstream_name in self.heads:
                    if latest_head > self.heads[upstream_name]:
                        self.heads[upstream_name] = latest_head
                        self._has_been_prompted.set()
                else:
                    self.heads[upstream_name] = latest_head
                    self._has_been_prompted.set()
        else:
            self._has_been_prompted.set()

    def _process_prompts(self) -> None:
        # Loop until stop event is set.
        self.positions_initialised.wait()

        while not self.has_been_stopped.is_set():
            try:
                self.__process_prompts()
            except Exception as e:
                if not self.has_been_stopped.is_set():
                    print(traceback.format_exc())
                    print("Continuing after error in 'process prompts' thread:", e)
                    print()
                    sleep(1)

    def __process_prompts(self):
        # Wait until prompted.
        self._has_been_prompted.wait()

        # self.print_timecheck('has been prompted')
        current_heads = {}
        with self.heads_lock:
            self._has_been_prompted.clear()
            for upstream_name in self.upstream_processes.keys():
                current_head = self.heads.get(upstream_name)
                current_heads[upstream_name] = current_head

        for upstream_name in self.upstream_processes.keys():

            with self.positions_lock:
                current_position = self.positions.get(upstream_name)
            first_id = current_position + 1  # request the next one

            current_head = current_heads[upstream_name]
            if current_head is None:
                last_id = None
            elif current_position < current_head:
                if GREEDY_PULL_NOTIFICATIONS:
                    last_id = first_id + PAGE_SIZE - 1
                else:
                    last_id = min(current_head, first_id + PAGE_SIZE - 1)
            else:
                # self.print_timecheck(
                #     "Up to date with", upstream_name, current_position,
                #     current_head
                # )
                continue
                # last_id = first_id + PAGE_SIZE - 1

            # self.print_timecheck(
            #     "Getting notifications in range:",
            #     upstream_name,
            #     "%s -> %s" % (first_id, last_id),
            # )
            upstream_process = self.upstream_processes[upstream_name]
            # Works best without prompted head as last requested,
            # because there might be more notifications since.
            # Todo: However, limit the number to avoid getting too many, and
            #  if we got full quota, then get again.

            notifications = []
            if PROMPT_WITH_NOTIFICATION_IDS or PROMPT_WITH_NOTIFICATION_OBJS:
                if last_id is not None:
                    for notification_id in range(first_id, last_id + 1):
                        if PROMPT_WITH_NOTIFICATION_IDS:
                            try:
                                rayid = self._notification_rayids.pop(
                                    (upstream_name, notification_id)
                                )
                            except KeyError:
                                break
                            else:
                                notification = ray.get(rayid)
                                # self._print_timecheck(
                                #     "Got notification from ray id",
                                #     notification_id,
                                #     rayid,
                                #     notification,
                                # )
                                notifications.append(notification)
                        elif PROMPT_WITH_NOTIFICATION_OBJS:
                            try:
                                notification = self._prompted_notifications.pop(
                                    (upstream_name, notification_id)
                                )
                                # self._print_timecheck(
                                #     "Got notification from prompted notifications dict",
                                #     notification_id,
                                #     notification,
                                # )
                            except KeyError:
                                break
                            else:
                                notifications.append(notification)
                        first_id += 1

            # Pull the ones we don't have.
            if last_id is None or first_id <= last_id:
                # self._print_timecheck("Pulling notifications", first_id, last_id,
                # 'from', upstream_name)
                rayid = upstream_process.get_notifications.remote(first_id, last_id)
                _notifications = ray.get(rayid)
                # self._print_timecheck("Pulled notifications", _notifications)
                notifications += _notifications

            # self.print_timecheck(
            #     "Obtained notifications:", len(notifications), 'from',
            #     upstream_name
            # )

            if len(notifications):

                if len(notifications) == PAGE_SIZE:
                    # self._print_timecheck("Range limit reached, reprompting...")
                    self._has_been_prompted.set()

                position = notifications[-1]["id"]
                with self.positions_lock:
                    current_position = self.positions[upstream_name]
                    if current_position is None or position > current_position:
                        self.positions[upstream_name] = position

            queue_item = []
            for notification in notifications:
                # Check causal dependencies.
                self.process_application.check_causal_dependencies(
                    upstream_name, notification.get("causal_dependencies")
                )
                # Get domain event from notification.
                event = self.process_application.get_event_from_notification(
                    notification
                )
                # self.print_timecheck("obtained event", event)

                # Put domain event on the queue, for event processing.
                queue_item.append((event, notification["id"], upstream_name))
            self.upstream_event_queue.put(queue_item)
            sleep(MICROSLEEP)

    def get_notifications(self, first_notification_id, last_notification_id):
        """
        Returns a list of notifications, with IDs from first_notification_id
        to last_notification_id, inclusive. IDs are 1-based sequence.

        This is called by the "process prompts" thread of a downstream process.
        """
        return self.do_db_job(
            self._get_notifications, (first_notification_id, last_notification_id), {}
        )

    def _get_notifications(self, first_notification_id, last_notification_id):
        record_manager = self.process_application.event_store.record_manager
        assert isinstance(record_manager, RecordManagerWithNotifications)
        start = first_notification_id - 1
        stop = last_notification_id
        return list(record_manager.get_notifications(start, stop))

    def _process_events(self):
        while not self.has_been_stopped.is_set():
            try:
                self.__process_events()
            except Exception as e:
                print(traceback.format_exc())
                print("Continuing after error in 'process events' thread:", e)
                sleep(1)

    def __process_events(self):
        try:
            queue_item = self.upstream_event_queue.get()  # timeout=5)
            self.upstream_event_queue.task_done()
        except Empty:
            if self.has_been_stopped.is_set():
                return
        else:
            if queue_item is None or self.has_been_stopped.is_set():
                return

            for (domain_event, notification_id, upstream_name) in queue_item:
                # print("Processing upstream event:", (domain_event,
                # notification_id, upstream_name))

                new_events, new_records = (), ()
                while not self.has_been_stopped.is_set():
                    try:
                        new_events, new_records = self.do_db_job(
                            method=self.process_application.process_upstream_event,
                            args=(domain_event, notification_id, upstream_name),
                            kwargs={},
                        )
                        break
                    except Exception as e:
                        print(traceback.format_exc())
                        self._print_timecheck(
                            "Retrying to reprocess event after error:", e
                        )
                        sleep(1)
                        # Todo: Forever? What if this is the wrong event?

                if self.has_been_stopped.is_set():
                    return

                # if new_events:
                #     self._print_timecheck("new events", len(new_events), new_events)

                notifications = ()
                notification_ids = ()
                notifiable_events = [e for e in new_events if e.__notifiable__]
                if len(notifiable_events):
                    if PROMPT_WITH_NOTIFICATION_IDS or PROMPT_WITH_NOTIFICATION_OBJS:
                        manager = self.process_application.event_store.record_manager
                        assert isinstance(manager, RecordManagerWithNotifications)
                        notification_id_name = manager.notification_id_name
                        notifications = []
                        for record in new_records:
                            if isinstance(
                                getattr(record, notification_id_name, None), int
                            ):
                                notifications.append(
                                    manager.create_notification_from_record(record)
                                )
                        if len(notifications):
                            head_notification_id = notifications[-1]["id"]
                            if PROMPT_WITH_NOTIFICATION_IDS:
                                notification_ids = self._put_notifications_in_ray_object_store(
                                    notifications
                                )
                                # Clear the notifications, avoid sending with IDs.
                                notifications = ()
                        else:
                            head_notification_id = self._get_max_notification_id()
                    else:
                        head_notification_id = self._get_max_notification_id()

                    prompt = RayPrompt(
                        self.process_application.name,
                        self.process_application.pipeline_id,
                        head_notification_id,
                        notification_ids,
                        notifications,
                    )

                    # self.print_timecheck(
                    #     "putting prompt on downstream " "prompt queue",
                    #     self.downstream_prompt_queue.qsize(),
                    # )
                    self.downstream_prompt_queue.put(prompt)
                    sleep(MICROSLEEP)
                    # self.print_timecheck(
                    #     "put prompt on downstream prompt " "queue"
                    # )
        # sleep(0.1)

    def _put_notifications_in_ray_object_store(self, notifications):
        notification_ids = [(n["id"], ray.put(n)) for n in notifications]
        return notification_ids

    def _enqueue_prompt_to_pull(self, prompt):
        # print("Enqueing locally published prompt:", prompt)
        self.downstream_prompt_queue.put(prompt)
        sleep(MICROSLEEP)

    def _push_prompts(self) -> None:
        while not self.has_been_stopped.is_set():
            try:
                self.__push_prompts()
            except Exception as e:
                print(traceback.format_exc())
                print("Continuing after error in 'push prompts' thread:", e)
                sleep(1)

    def __push_prompts(self):
        try:
            item = self.downstream_prompt_queue.get()  # timeout=1)
            self.downstream_prompt_queue.task_done()
            # Todo: Instead, drain the queue and consolidate prompts.
        except Empty:
            self._print_timecheck(
                "timed out getting item from downstream prompt " "queue"
            )
            if self.has_been_stopped.is_set():
                return
        else:
            # self.print_timecheck("task done on downstream prompt queue")
            if item is None or self.has_been_stopped.is_set():
                return
            elif isinstance(item, PromptToPull):
                if item.head_notification_id:
                    head_notification_id = item.head_notification_id
                else:
                    head_notification_id = self._get_max_notification_id()
                prompt = RayPrompt(
                    self.process_application.name,
                    self.process_application.pipeline_id,
                    head_notification_id,
                )
            else:
                prompt = item
            # self._print_timecheck('pushing prompt with', prompt.notification_ids)
            prompt_response_ids = []
            # self.print_timecheck("pushing prompts", prompt)
            for downstream_name, ray_process in self.downstream_processes.items():
                prompt_response_ids.append(ray_process.prompt.remote(prompt))
                if self.has_been_stopped.is_set():
                    return
                # self._print_timecheck("pushed prompt to", downstream_name)
            ray.get(prompt_response_ids)
            # self._print_timecheck("pushed prompts")

    def _get_max_notification_id(self):
        """
        Returns the highest notification ID of this process application.
        :return:
        """
        record_manager = self.process_application.event_store.record_manager
        assert isinstance(record_manager, RecordManagerWithNotifications)
        max_notification_id = self.do_db_job(
            record_manager.get_max_notification_id, (), {}
        )
        # self.print_timecheck("MAX NOTIFICATION ID in DB:", max_notification_id)
        return max_notification_id

    def stop(self):
        """
        Stops the process.
        """
        self.has_been_stopped.set()
        self.process_application.close()
        unsubscribe(handler=self._enqueue_prompt_to_pull, predicate=is_prompt_to_pull)

    def _print_timecheck(self, activity, *args):
        # pass
        process_name = self.application_process_class.__name__.lower()
        print(
            "Timecheck",
            datetime.datetime.now(),
            self.pipeline_id,
            process_name,
            activity,
            *args
        )


class ProcessApplicationProxy:
    def __init__(self, ray_process: RayProcess):
        self.ray_process: RayProcess = ray_process

    def __getattr__(self, item):
        return AttributeProxy(self.ray_process, item)


class AttributeProxy:
    def __init__(self, ray_process: RayProcess, attribute_name: str):
        self.ray_process: RayProcess = ray_process
        self.attribute_name = attribute_name

    def __call__(self, *args, **kwargs):
        ray_id = self.ray_process.call.remote(self.attribute_name, *args, **kwargs)
        return_value = ray.get(ray_id)
        if isinstance(return_value, ExceptionWrapper):
            raise return_value.e
        else:
            return return_value
