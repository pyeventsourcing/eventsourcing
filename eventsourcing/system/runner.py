import time
from abc import abstractmethod
from collections import defaultdict, deque
from queue import Empty, Queue
from threading import Barrier, BrokenBarrierError, Event, Lock, Thread, Timer
from time import sleep
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Deque,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    Union,
    no_type_check,
)

from eventsourcing.application.notificationlog import NotificationLogReader
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
    EventSourcingError,
    OperationalError,
    ProgrammingError,
    RecordConflictError,
)
from eventsourcing.system.definition import AbstractSystemRunner, System
from eventsourcing.whitehead import T

DEFAULT_POLL_INTERVAL = 5


# Todo: Support passing SQLAlchemy session into runner.
class InProcessRunner(AbstractSystemRunner):
    """
    Runs a system in the current process,
    either in the current thread, or with
    one thread for each process in the system.
    """

    def start(self) -> None:
        if len(self.processes):
            raise ProgrammingError("Already running")

        # Construct the processes.
        for process_class in self.system.process_classes.values():
            self._construct_app_by_class(process_class)

        # Tell each process which other processes to follow.
        for downstream_name, upstream_names in self.system.upstream_names.items():
            downstream_process = self.processes[downstream_name]
            for upstream_name in upstream_names:
                upstream_process = self.processes[upstream_name]
                upstream_log = upstream_process.notification_log
                downstream_process.follow(upstream_name, upstream_log)

        # Do something to propagate prompts.
        subscribe(predicate=is_prompt_to_pull, handler=self.handle_prompt)

    @abstractmethod
    def handle_prompt(self, prompt: Prompt) -> None:
        """
        Handles publication of a prompt.

        Abstract method which must be implemented on concrete descendants.
        """

    def close(self) -> None:
        super(InProcessRunner, self).close()

        unsubscribe(predicate=is_prompt_to_pull, handler=self.handle_prompt)


class SingleThreadedRunner(InProcessRunner):
    """
    Runs a system in the current thread.
    """

    def __init__(
        self,
        system: System,
        infrastructure_class: Optional[
            Type[ApplicationWithConcreteInfrastructure]
        ] = None,
        **kwargs: Any,
    ):
        super(SingleThreadedRunner, self).__init__(
            system, infrastructure_class=infrastructure_class, **kwargs
        )
        if TYPE_CHECKING:
            self.pending_prompts: Queue[Prompt]
        self.pending_prompts = Queue()

        self.iteration_lock = Lock()

    def handle_prompt(self, prompt: Prompt) -> None:
        self.run_followers(prompt)

    def run_followers(self, prompt: Prompt) -> None:
        """
        First caller adds a prompt to queue and
        runs followers until there are no more
        pending prompts.

        Subsequent callers just add a prompt
        to the queue, avoiding recursion.
        """
        # Put the prompt on the queue.
        self.pending_prompts.put(prompt)

        if self.iteration_lock.acquire(False):
            # start_time = time.time()
            i = 0
            try:
                while True:
                    try:
                        prompt = self.pending_prompts.get(False)
                    except Empty:
                        break
                    else:
                        if isinstance(prompt, PromptToPull):
                            downstream_names = self.system.downstream_names[
                                prompt.process_name
                            ]
                            for downstream_name in downstream_names:
                                downstream_process = self.processes[downstream_name]
                                downstream_process.run(prompt)
                                i += 1
                        self.pending_prompts.task_done()
            finally:
                # run_frequency = i / (time.time() - start_time)
                # print(f"Run frequency: {run_frequency}")
                self.iteration_lock.release()


class MultiThreadedRunner(InProcessRunner):
    """
    Runs a system with a thread for each process.
    """

    def __init__(
        self,
        system: System,
        poll_interval: Optional[int] = None,
        clock_speed: Optional[Union[int, float]] = None,
        **kwargs: Any,
    ):
        super(MultiThreadedRunner, self).__init__(system=system, **kwargs)
        self.poll_interval = poll_interval or DEFAULT_POLL_INTERVAL
        assert isinstance(system, System)
        self.threads: Dict[str, PromptQueuedApplicationThread] = {}
        self.clock_speed: Optional[Union[float, int]] = clock_speed
        if self.clock_speed:
            self.clock_event = Event()
            self.stop_clock_event = Event()

        self.inboxes: Dict[str, Queue] = {}
        self.outboxes: Dict[str, PromptOutbox[str]] = {}

    def start(self) -> None:
        super(MultiThreadedRunner, self).start()
        assert not self.threads, "Already started"
        assert not self.inboxes, "Already has inboxes"
        assert not self.outboxes, "Already has outboxes"

        # Setup queues.
        for process_name, upstream_names in self.system.upstream_names.items():
            inbox_id = process_name.lower()
            if inbox_id not in self.inboxes:
                self.inboxes[inbox_id] = Queue()
            for upstream_class_name in upstream_names:
                outbox_id = upstream_class_name.lower()
                if outbox_id not in self.outboxes:
                    self.outboxes[outbox_id] = PromptOutbox()
                if inbox_id not in self.outboxes[outbox_id].downstream_inboxes:
                    self.outboxes[outbox_id].downstream_inboxes[
                        inbox_id
                    ] = self.inboxes[inbox_id]

        # Construct application threads.
        for process_name, process in self.processes.items():
            if self.clock_speed:
                process.clock_event = self.clock_event
                process.tick_interval = 1 / self.clock_speed

            thread = PromptQueuedApplicationThread(
                process=process,
                poll_interval=self.poll_interval,
                inbox=self.inboxes[process_name],
                outbox=self.outboxes.get(process_name),
                # Todo: Is it better to clock the prompts or the notifications?
                # clock_event=clock_event
            )
            self.threads[process_name] = thread

        # Start application threads.
        for thread in self.threads.values():
            thread.start()

        for thread in self.threads.values():
            thread.is_running.wait()

        # Start clock.
        if self.clock_speed:
            self.start_clock()

    def start_clock(self) -> None:
        assert self.clock_speed, self.clock_speed
        tick_interval = 1 / self.clock_speed
        # print(f"Tick interval: {tick_interval:.6f}s")
        self.last_tick = None
        self.this_tick = None
        self.tick_adjustment = 0

        def set_clock_event() -> None:
            if self.stop_clock_event.is_set():
                return

            self.this_tick = time.process_time()

            if self.last_tick:
                tick_size = self.this_tick - self.last_tick

                tick_oversize = tick_size - tick_interval
                tick_oversize_percentage = 100 * (tick_oversize) / tick_interval
                if tick_oversize_percentage > 300:
                    print(
                        f"Warning: Tick over size: {tick_size :.6f}s "
                        f"{tick_oversize_percentage:.2f}%"
                    )

                if abs(tick_oversize_percentage) < 300:
                    self.tick_adjustment += 0.5 * tick_interval * tick_oversize
                    max_tick_adjustment = 0.5 * tick_interval
                    min_tick_adjustment = 0
                    self.tick_adjustment = min(
                        self.tick_adjustment, max_tick_adjustment
                    )
                    self.tick_adjustment = max(
                        self.tick_adjustment, min_tick_adjustment
                    )

            self.last_tick = self.this_tick

            self.clock_event.set()
            self.clock_event.clear()

            if not self.stop_clock_event.is_set():
                set_timer()

        def set_timer() -> None:
            # print(f"Tick adjustment: {self.tick_adjustment:.6f}")
            if self.last_tick is not None:
                time_since_last_tick = time.process_time() - self.last_tick
                time_remaining = tick_interval - time_since_last_tick
                timer_interval = time_remaining - self.tick_adjustment
                if timer_interval < 0:
                    timer_interval = 0
                    # print("Warning: clock thread is running flat out!")
            else:
                timer_interval = 0
            timer = Timer(timer_interval, set_clock_event)
            timer.start()

        set_timer()

    def handle_prompt(self, prompt: Prompt) -> None:
        self.broadcast_prompt(prompt)

    def broadcast_prompt(self, prompt: Prompt) -> None:
        if isinstance(prompt, PromptToPull):
            outbox_id = prompt.process_name
            outbox = self.outboxes.get(outbox_id)
            if outbox:
                outbox.put(prompt)

    def close(self) -> None:
        super(MultiThreadedRunner, self).close()

        if self.clock_speed:
            self.clock_event.set()
            self.stop_clock_event.set()

        for thread in self.threads.values():
            thread.inbox.put(PromptToQuit())

        for thread in self.threads.values():
            thread.join(timeout=10)

        self.threads.clear()
        self.outboxes.clear()
        self.inboxes.clear()


class PromptOutbox(Generic[T]):
    """
    Has a collection of downstream prompt inboxes.

    """

    def __init__(self) -> None:
        self.downstream_inboxes: Dict[T, Queue] = {}

    def put(self, prompt: Union[PromptToPull, str]) -> None:
        """
        Puts prompt in each downstream inbox (an actual queue).
        """
        for queue in self.downstream_inboxes.values():
            queue.put(prompt)


class PromptQueuedApplicationThread(Thread):
    """
    Application thread which uses queues of prompts.

    It loops on an "inbox" queue of prompts, and
    adds its prompts to an "outbox" queue.
    """

    def __init__(
        self,
        *,
        process: ProcessApplication,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        inbox: Queue,
        outbox: Optional[PromptOutbox],
        clock_event: Optional[Event] = None,
    ):
        """
        Initialises the thread with a process application object, and
        inbox and outbox.

        :param ProcessApplication process: Application object.
        :param int poll_interval: Interval to check for upstream events.
        :param Queue inbox: For incoming prompts.
        :param PromptOutbox outbox: For outgoing prompts.
        :param clock_event: Event that "clocks" this thread (optional).
        """
        super(PromptQueuedApplicationThread, self).__init__(daemon=True)
        self.app = process
        self.poll_interval = poll_interval
        if TYPE_CHECKING:
            self.inbox: Queue[Union[Prompt, str]]
        self.inbox = inbox
        self.outbox = outbox
        self.clock_event = clock_event
        self.is_running = Event()

    def run(self) -> None:
        self.loop_on_prompts()

    def loop_on_prompts(self) -> None:

        # Loop on getting prompts.
        self.is_running.set()
        while True:
            try:
                # Todo: Make the poll interval gradually
                #  increase if there are only timeouts?
                prompt = self.inbox.get(timeout=self.poll_interval)

            except Empty:
                # Basically, we're polling after a timeout.
                if self.clock_event is None:
                    self.run_process()

            else:
                self.inbox.task_done()

                if isinstance(prompt, PromptToQuit):
                    self.app.close()
                    break

                elif isinstance(prompt, PromptToPull):
                    started = None
                    if self.clock_event is not None:
                        self.clock_event.wait()
                        started = time.time()

                    self.run_process(prompt)

                    if self.clock_event is not None:
                        assert started
                        ended = time.time()
                        duration = ended - started
                        if self.clock_event.is_set():
                            print(
                                f"Warning: Process {self.app.name} overran clock "
                                f"cycle: {duration}"
                            )
                        else:
                            print(
                                f"Info: Process {self.app.name} ran within clock "
                                f"cycle: {duration}"
                            )
                else:
                    raise Exception("Unsupported prompt: {}".format(prompt))

    def run_process(self, prompt: Optional[PromptToPull] = None) -> None:
        try:
            self._run_process(prompt)
        except CausalDependencyFailed:
            pass
        except EventSourcingError:
            pass

    @retry(CausalDependencyFailed, max_attempts=100, wait=0.2)
    @retry((OperationalError, RecordConflictError), max_attempts=100, wait=0.01)
    def _run_process(self, prompt: Optional[PromptToPull] = None) -> None:
        self.app.run(prompt)


class SteppingRunner(InProcessRunner):
    def __init__(
        self,
        normal_speed: int = 1,
        scale_factor: int = 1,
        is_verbose: bool = False,
        *args: Any,
        **kwargs: Any,
    ):
        super(SteppingRunner, self).__init__(*args, **kwargs)
        self.normal_speed = normal_speed
        self.scale_factor = scale_factor
        self.is_verbose = is_verbose
        if scale_factor:
            self.tick_interval = 1 / (normal_speed * scale_factor)
        else:
            self.tick_interval = 0
        if self.is_verbose:
            print(f"Tick interval: {self.tick_interval:.6f}s")
        self.clock_thread: Optional[ClockThread] = None

    def call_in_future(self, cmd: Callable, ticks_delay: int) -> None:
        assert self.clock_thread
        self.clock_thread.call_in_future(cmd, ticks_delay)


class SteppingSingleThreadedRunner(SteppingRunner):
    def __init__(self, *args: Any, **kwargs: Any):
        super(SteppingSingleThreadedRunner, self).__init__(*args, **kwargs)
        self.seen_prompt_events: Dict[str, Event] = {}
        self.stop_event = Event()

    def start(self) -> None:
        super(SteppingSingleThreadedRunner, self).start()

        self.clock_thread = ProcessRunningClockThread(
            normal_speed=self.normal_speed,
            scale_factor=self.scale_factor,
            stop_event=self.stop_event,
            is_verbose=self.is_verbose,
            seen_prompt_events=self.seen_prompt_events,
            processes=self.processes,
            use_direct_query_if_available=self.use_direct_query_if_available,
        )
        self.clock_thread.start()

    def handle_prompt(self, prompt: Prompt) -> None:
        """
        Ignores prompts.
        """

    def close(self) -> None:
        self.stop_event.set()
        super(SteppingSingleThreadedRunner, self).close()
        if self.clock_thread:
            self.clock_thread.join(5)
            if self.clock_thread.is_alive():
                print("Warning: clock thread was still alive")


class ClockThread(Thread):
    def __init__(self, *args: Any, **kwargs: Any):
        super(ClockThread, self).__init__()
        self.future_cmds: Dict[int, List[Callable]] = defaultdict(list)
        self.tick_count = 0

    def call_in_future(self, cmd: Callable, ticks_delay: int) -> None:
        ticks_delay = max(ticks_delay, 1)
        self.future_cmds[ticks_delay + self.tick_count].append(cmd)

    def call_commands(self) -> None:
        for future_cmd in self.future_cmds.get(self.tick_count, []):
            future_cmd()

    @no_type_check
    def do_tick(self, process_time: float, tick_time: float) -> None:
        # Todo: Pull these members up from subclasses.
        tick_duration = tick_time - self.last_tick_time
        self.all_tick_durations.append(tick_duration)
        if len(self.all_tick_durations) > self.tick_durations_window_size:
            self.all_tick_durations.popleft()
        if self.is_verbose:
            process_duration = process_time - self.last_process_time
            intensity = 100 * process_duration / tick_duration
            clock_speed = 1 / tick_duration
            real_time = self.tick_count / self.normal_speed
            print(
                f"Tick {self.tick_count:4}: {real_time:4.2f}s  "
                f"{tick_duration:.6f}s, "
                f"{intensity:6.2f}%, {clock_speed:6.1f}Hz, "
                f"{self.actual_clock_speed:6.1f}Hz, "
                f"{self.tick_adjustment:.6f}s"
            )
        if self.tick_interval:
            tick_oversize = tick_duration - self.tick_interval
            tick_oversize_percentage = 100 * (tick_oversize) / self.tick_interval
            # if tick_oversize_percentage > 300:
            #     print(f"Warning: Tick over size: { tick_duration :.6f}s
            #     {tick_oversize_percentage:.2f}%")

            if abs(tick_oversize_percentage) < 300:
                # Weight falls from 1 as reciprocal of count, to tick
                # interval.
                # weight = max(1 / self.tick_count, min(.1,
                # self.tick_interval))
                weight = 1 / (1 + self.tick_count * self.tick_interval) ** 2
                # print(f"Weight: {weight:.4f}")
                self.tick_adjustment += weight * tick_oversize
                max_tick_adjustment = 1.0 * self.tick_interval
                min_tick_adjustment = 0
                self.tick_adjustment = min(self.tick_adjustment, max_tick_adjustment)
                self.tick_adjustment = max(self.tick_adjustment, min_tick_adjustment)


class ProcessRunningClockThread(ClockThread):
    def __init__(
        self,
        *,
        normal_speed: int,
        scale_factor: int,
        stop_event: Event,
        is_verbose: bool = False,
        seen_prompt_events: Dict[str, Event],
        processes: Dict[str, ProcessApplication],
        use_direct_query_if_available: bool = False,
    ):
        super(ProcessRunningClockThread, self).__init__(daemon=True)
        self.normal_speed = normal_speed
        self.scale_factor = scale_factor
        self.stop_event = stop_event
        self.seen_prompt_events = seen_prompt_events
        self.processes = processes
        self.use_direct_query_if_available = use_direct_query_if_available
        self.last_tick_time: Union[float, int] = 0
        self.last_process_time = 0.0
        self.all_tick_durations: Deque = deque()
        self.tick_adjustment: float = 0.0
        self.is_verbose = is_verbose
        if normal_speed and scale_factor:
            self.tick_interval = 1 / normal_speed / scale_factor
            self.tick_durations_window_size = max(
                100, int(round(1 / self.tick_interval, 0))
            )
        else:
            self.tick_interval = 0
            self.tick_durations_window_size = 1000
        # Construct lists of followers for each process.
        self.followers: Dict[str, List[str]] = {}
        for process in self.processes.values():
            self.followers[process.name] = []
        for process in self.processes.values():
            for upstream_process_name in process.readers:
                self.followers[upstream_process_name].append(process.name)

        # Construct a notification log reader for each process.
        self.readers: Dict[str, NotificationLogReader] = {}
        for process in self.processes.values():
            reader = process.notification_log_reader_class(
                notification_log=process.notification_log,
                use_direct_query_if_available=self.use_direct_query_if_available,
            )
            self.readers[process.name] = reader

    @property
    def actual_clock_speed(self) -> Union[int, float]:
        if self.all_tick_durations:
            # Todo: Might need to lock this, to avoid "RuntimeError: deque mutated
            #  during iteration".
            durations = list(self.all_tick_durations)
            return len(durations) / sum(durations)
        else:
            return 0

    def run(self) -> None:
        # Get new notifications once.

        # loop_counter = 0

        while not self.stop_event.is_set():
            # print("Loop count: {}".format(loop_counter))
            try:
                # Get all notifications.
                all_notifications = {}
                for process_name in self.processes:
                    # seen_prompt = self.seen_prompt_events[process_name]
                    # if seen_prompt.is_set():
                    #     seen_prompt.clear()
                    reader = self.readers[process_name]
                    notifications = reader.list_notifications()
                    all_notifications[process_name] = notifications

                # Process all notifications.
                all_events = {}
                for process_name, notifications in all_notifications.items():
                    events = []
                    for notification in notifications:
                        # print(process_name, notification)
                        process = self.processes[process_name]
                        # It's not the follower process, but the method does the same
                        # thing.
                        event = process.get_event_from_notification(notification)
                        notification_id = notification["id"]
                        events.append((notification_id, event))
                    all_events[process_name] = events

                for process_name, events in all_events.items():
                    # print(f"Process: {process_name}")
                    for follower_name in self.followers[process_name]:
                        follower_process = self.processes[follower_name]
                        # print(f"Follower: {follower_name}")
                        for notification_id, event in events:
                            # print(f"Notification: {notification_id}, {event}")
                            follower_process.process_upstream_event(
                                event, notification_id, process_name
                            )
                # Call commands delayed until this clock tick.
                self.call_commands()

            except:
                if self.stop_event.is_set():
                    break
                else:
                    # print("Error... Loop count: {}".format(loop_counter))
                    self.stop_event.set()
                    raise
            else:
                tick_time: float = time.time()
                process_time = time.process_time()
                if self.last_tick_time:
                    self.do_tick(process_time, tick_time)

                self.last_tick_time = tick_time
                self.last_process_time = process_time
                self.tick_count += 1

                if self.tick_interval:
                    sleep_interval = self.tick_interval - self.tick_adjustment
                    sleep(max(sleep_interval, 0))


class SteppingMultiThreadedRunner(SteppingRunner):
    """
    Has a clock thread, and a thread for each application process
    in the system. The clock thread loops until stopped, waiting
    for a barrier, after sleeping for remaining tick interval timer.
    Application threads loop until stopped, waiting for the same
    barrier. Then, after all threads are waiting at the barrier,
    the barrier is lifted. The clock thread proceeds by sleeping
    for the clock tick interval. The application threads proceed by
    getting new notifications and processing all of them.

    There are actually two barriers, so that each application thread
    waits before getting notifications, and then waits for all processes
    to complete getting notification before processing the notifications
    through the application policy. This avoids events created by a process
    application "bleeding" into the notifications of another process
    application in the same clock cycle.


    Todo:
    Receive prompts, but set an event for the prompting process, to avoid unnecessary
    runs.

    Allow commands to be scheduled at future clock tick number, and execute when
    reached.

    """

    def __init__(self, *args: Any, **kwargs: Any):
        super(SteppingMultiThreadedRunner, self).__init__(*args, **kwargs)
        self.seen_prompt_events: Dict[str, Event] = {}
        self.fetch_barrier: Optional[Barrier] = None
        self.execute_barrier: Optional[Barrier] = None
        self.application_threads: Dict[str, BarrierControlledApplicationThread] = {}
        self.clock_thread = None
        self.stop_event = Event()

    def handle_prompt(self, prompt: Prompt) -> None:
        if isinstance(prompt, PromptToPull):
            seen_prompt = self.seen_prompt_events[prompt.process_name]
            seen_prompt.set()

    def start(self) -> None:
        super(SteppingMultiThreadedRunner, self).start()
        parties = 1 + len(self.processes)
        self.fetch_barrier = Barrier(parties)
        self.execute_barrier = Barrier(parties)

        # Create an event for each process.
        for process_name in self.processes:
            self.seen_prompt_events[process_name] = Event()

        # Construct application threads.
        for process_name, process in self.processes.items():
            process_instance_id = process_name

            thread = BarrierControlledApplicationThread(
                process=process,
                fetch_barrier=self.fetch_barrier,
                execute_barrier=self.execute_barrier,
                stop_event=self.stop_event,
            )
            self.application_threads[process_instance_id] = thread

        # Start application threads.
        for thread in self.application_threads.values():
            thread.start()

        # Start clock thread.
        self.clock_thread = BarrierControllingClockThread(
            normal_speed=self.normal_speed,
            scale_factor=self.scale_factor,
            tick_interval=self.tick_interval,
            fetch_barrier=self.fetch_barrier,
            execute_barrier=self.execute_barrier,
            stop_event=self.stop_event,
            is_verbose=self.is_verbose,
        )
        self.clock_thread.start()

    def close(self) -> None:
        self.stop_event.set()
        super(SteppingMultiThreadedRunner, self).close()
        if self.execute_barrier:
            self.execute_barrier.abort()
        if self.fetch_barrier:
            self.fetch_barrier.abort()

        for thread in self.application_threads.values():
            thread.join(timeout=1)
            if thread.is_alive():
                print(
                    f"Warning: application thread '"
                    f"{thread.app.name}"
                    f"' was still alive."
                )

        self.application_threads.clear()

        if self.clock_thread:
            self.clock_thread.join(timeout=1)
            if self.clock_thread.is_alive():
                print(f"Warning: clock thread was still alive")


class BarrierControlledApplicationThread(Thread):
    def __init__(
        self,
        process: ProcessApplication,
        fetch_barrier: Barrier,
        execute_barrier: Barrier,
        stop_event: Event,
    ):
        super(BarrierControlledApplicationThread, self).__init__(daemon=True)
        self.app = process
        self.fetch_barrier = fetch_barrier
        self.execute_barrier = execute_barrier
        self.stop_event = stop_event

    def run(self) -> None:
        while not self.stop_event.is_set():
            # Isolate "fetch" and "execute" steps, to avoid
            # events created in one application being processed by
            # another application in the same tick. Race condition
            # where one process writes new events before another has
            # read all notifications from last tick. Actually, need
            # to get all notifications from all upstream applications
            # and then process the notifications. The run() method
            # gets notifications from one, then processes, then gets
            # from another, which makes the race condition probable.
            all_notifications = []
            try:
                self.fetch_barrier.wait()
            except BrokenBarrierError:
                self.abort()
            else:
                try:
                    # Get all notifications.
                    for upstream_name in self.app.readers:
                        notifications = list(self.app.read_reader(upstream_name))
                        all_notifications.append((upstream_name, notifications))

                except:
                    self.abort()
                    raise

            if self.stop_event.is_set():
                break

            try:
                self.execute_barrier.wait()
            except BrokenBarrierError:
                self.abort()
            else:
                try:
                    # Process all notifications.
                    for upstream_name, notifications in all_notifications:
                        for notification in notifications:
                            event = self.app.get_event_from_notification(notification)
                            self.app.process_upstream_event(
                                event, notification["id"], upstream_name
                            )
                except:
                    self.abort()
                    raise

            try:
                self.execute_barrier.wait()
            except BrokenBarrierError:
                self.abort()

    def abort(self) -> None:
        self.stop_event.set()
        self.fetch_barrier.abort()
        self.execute_barrier.abort()


class BarrierControllingClockThread(ClockThread):
    def __init__(
        self,
        normal_speed: int,
        scale_factor: int,
        tick_interval: Optional[Union[int, float]],
        fetch_barrier: Barrier,
        execute_barrier: Barrier,
        stop_event: Event,
        is_verbose: bool = False,
    ):
        super(BarrierControllingClockThread, self).__init__(daemon=True)
        # Todo: Remove the redundancy here.
        self.normal_speed = normal_speed
        self.scale_factor = scale_factor
        self.tick_interval = tick_interval
        self.fetch_barrier = fetch_barrier
        self.execute_barrier = execute_barrier
        self.stop_event = stop_event
        self.last_tick_time = 0.0
        self.last_process_time = 0.0
        self.all_tick_durations: Deque = deque()
        self.tick_adjustment: float = 0.0
        self.is_verbose = is_verbose
        if self.tick_interval:

            self.tick_durations_window_size = max(
                1, int(round(1 / self.tick_interval, 0))
            )
        else:
            self.tick_durations_window_size = 100

    @property
    def actual_clock_speed(self) -> float:
        if self.all_tick_durations:
            durations = self.all_tick_durations
            return len(durations) / sum(durations)
        else:
            return 0.0

    def run(self) -> None:
        while not self.stop_event.is_set():

            try:
                self.fetch_barrier.wait()
                self.execute_barrier.wait()
                self.execute_barrier.wait()
                self.call_commands()
            except BrokenBarrierError:
                self.fetch_barrier.abort()
                self.execute_barrier.abort()
                self.stop_event.set()
            else:
                tick_time = time.time()
                process_time = time.process_time()
                if self.last_tick_time:
                    self.do_tick(process_time, tick_time)

                self.last_tick_time = tick_time
                self.last_process_time = process_time
                self.tick_count += 1

                if self.tick_interval:
                    sleep_interval = self.tick_interval - self.tick_adjustment
                    sleep(max(sleep_interval, 0))
